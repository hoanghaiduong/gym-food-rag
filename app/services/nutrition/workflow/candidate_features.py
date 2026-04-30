from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition.knowledge.hint_matching import candidate_matches_runtime_hint
from app.services.nutrition_knowledge_service import ascii_normalize, safe_float
from app.services.nutrition.knowledge.exclusion_matching import payload_matches_exclusion

from .constants import (
    AFFORDABLE_FOOD_KEYWORDS,
    COMMON_MEAL_FOOD_KEYWORDS,
    LOW_PRACTICALITY_KEYWORDS,
    PREFERRED_CARB_KEYWORDS,
    PREFERRED_PROTEIN_KEYWORDS,
    REALISM_DISCOURAGED_NAME_KEYWORDS,
    REALISM_HARD_BLOCK_GROUP_KEYWORDS,
    REALISM_HARD_BLOCK_NAME_KEYWORDS,
)


class WorkflowCandidateFeaturesMixin:
    def _candidate_matches_hint(self, candidate: dict[str, Any], hint: str) -> bool:
        semantic_match = candidate_matches_runtime_hint(candidate, hint)
        if semantic_match is not None:
            return semantic_match
        return self._candidate_matches_hint_variants(candidate, self._expand_hint_variants(hint))

    def _candidate_matches_strict_hint(self, candidate: dict[str, Any], hint: str) -> bool:
        normalized_hint = ascii_normalize(hint)
        if not normalized_hint:
            return False
        return payload_matches_exclusion(candidate, normalized_hint)

    def _candidate_match_text(self, candidate: dict[str, Any]) -> str:
        candidate_text = " ".join(
            str(item)
            for item in [
                candidate.get("name") or candidate.get("food_name"),
                candidate.get("name_en"),
                candidate.get("group_name"),
                candidate.get("group_slug"),
                candidate.get("category_slug"),
                " ".join(candidate.get("diet_tags") or []),
                " ".join(candidate.get("ingredient_hints") or []),
            ]
            if item
        )
        return ascii_normalize(candidate_text)

    def _candidate_matches_hint_variants(self, candidate: dict[str, Any], variants: list[str]) -> bool:
        normalized_text = self._candidate_match_text(candidate)
        text_tokens = set(re.sub(r"[^a-z0-9]+", " ", normalized_text).split())
        for variant in variants:
            if not variant:
                continue
            variant_tokens = [token for token in re.sub(r"[^a-z0-9]+", " ", variant).split() if token]
            if not variant_tokens:
                continue
            if len(variant_tokens) == 1:
                if variant_tokens[0] in text_tokens:
                    return True
                continue
            if all(token in text_tokens for token in variant_tokens):
                return True
        return False

    def _candidate_source_name(self, candidate: dict[str, Any]) -> str:
        return str(
            candidate.get("source_food_name")
            or candidate.get("name")
            or candidate.get("food_name")
            or ""
        )

    def _is_inedible_raw_candidate(self, candidate: dict[str, Any]) -> bool:
        if candidate.get("final_output_allowed") is False:
            return True
        if candidate.get("consumption_state") == "direct_edible_raw":
            return False
        if candidate.get("consumption_state") == "requires_preparation":
            return True

        source_name = self._candidate_source_name(candidate)
        source_name_lower = source_name.lower()
        normalized_name = ascii_normalize(source_name)
        normalized_group = ascii_normalize(candidate.get("group_name"))
        name_tokens = set(re.sub(r"[^a-z0-9]+", " ", normalized_name).split())
        raw_marked = bool(re.search(r"(^|[\s,])sống($|[\s,])", source_name_lower))
        raw_marked = raw_marked or bool(re.search(r"(^|[\s,])raw($|[\s,])", source_name_lower))
        if not raw_marked and "song" in name_tokens and not re.search(r"(^|[\s,])sông($|[\s,])", source_name_lower):
            raw_marked = True

        if raw_marked:
            return True

        raw_grain_terms = {"gao", "nep", "lua"}
        if raw_marked and name_tokens.intersection(raw_grain_terms):
            return True
        if raw_marked and "ngu coc" in normalized_group:
            return True

        dry_marker = any(marker in normalized_name for marker in [", kho", " kho", "hat kho", "hat, kho"])
        dry_legume_terms = [
            "dau tuong",
            "dau nanh",
            "dau xanh",
            "dau den",
            "dau do",
            "dau trang",
            "dau ha lan",
            "dau lang",
            "au tuong",
            "au nanh",
            "au xanh",
            "au den",
            "au do",
            "au trang",
            "au ha lan",
            "au lang",
        ]
        if dry_marker and any(term in normalized_name for term in dry_legume_terms):
            return True

        flour_like = "bot" in name_tokens or normalized_name.startswith("bot ")
        if flour_like and any(group in normalized_group for group in ["ngu coc", "bot"]):
            return True

        return False

    def _candidate_realism_profile(
        self,
        candidate: dict[str, Any],
        goal: str,
        dietary_preference: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_name = ascii_normalize(self._candidate_source_name(candidate))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        diet_tags = set(candidate.get("diet_tags") or [])
        allergen_tags = set(candidate.get("allergen_tags") or [])
        energy = safe_float(candidate.get("energy_kcal"), 0.0)
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        fat = safe_float(candidate.get("fat_g"), 0.0)

        hard_block_reasons: list[str] = []
        discouraged_reasons: list[str] = []
        preferred_reasons: list[str] = []
        meal_readiness_tier = str(candidate.get("meal_readiness_tier") or "")
        meal_role_tags = set(candidate.get("meal_role_tags") or [])
        planner_rank_weight = safe_float(candidate.get("planner_rank_weight"), 0.0)
        consumption_state = str(candidate.get("consumption_state") or "")
        final_output_allowed = candidate.get("final_output_allowed")
        unsafe_output_reason = str(candidate.get("unsafe_output_reason") or "")
        produce_like = self._is_produce_like_candidate(candidate)
        portion_safe_nut_name = any(
            keyword in normalized_name
            for keyword in [
                "hat macca",
                "hat oc cho",
                "hat de cuoi",
                "hat huong duong",
                "hat bi do",
                "hat dieu",
            ]
        )
        protein_like_name = any(keyword in normalized_name for keyword in PREFERRED_PROTEIN_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["thit", "trung", "sua", "thuy san", "hat", "dau"]
        )
        carb_like_name = any(keyword in normalized_name for keyword in PREFERRED_CARB_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["khoai", "ngu coc", "bot", "banh mi"]
        )

        if final_output_allowed is False or consumption_state == "requires_preparation":
            hard_block_reasons.append(unsafe_output_reason or "unsafe_final_output")
        if self._is_inedible_raw_candidate(candidate):
            hard_block_reasons.append("inedible_raw_ingredient")
        hard_block_keyword_hit = False
        for keyword in REALISM_HARD_BLOCK_NAME_KEYWORDS:
            if keyword not in normalized_name:
                continue
            if keyword == "duong " and "huong duong" in normalized_name:
                continue
            hard_block_keyword_hit = True
            break
        if hard_block_keyword_hit:
            hard_block_reasons.append("condiment_or_flavoring")
        if any(keyword in normalized_group for keyword in REALISM_HARD_BLOCK_GROUP_KEYWORDS):
            hard_block_reasons.append("condiment_group")
        if any(keyword in normalized_name for keyword in [" bot", "bot ", ", kho", " kho,", " kho "]):
            hard_block_reasons.append("ingredient_or_dried_component")
        if goal == "lose_weight" and any(normalized_name.startswith(prefix) for prefix in ["che ", "banh ", "xoi "]):
            hard_block_reasons.append("dessert_like_for_weight_loss")
        if goal == "lose_weight" and normalized_name.startswith("com rang"):
            hard_block_reasons.append("fried_staple_for_weight_loss")

        if any(keyword in normalized_name for keyword in REALISM_DISCOURAGED_NAME_KEYWORDS):
            discouraged_reasons.append("specialty_or_low_practicality")
        if normalized_name.startswith(("banh ", "che ")) and protein < 10:
            discouraged_reasons.append("dessert_or_snack_like")
        if goal == "lose_weight" and normalized_name.startswith("xoi ") and protein < 10:
            discouraged_reasons.append("dessert_or_snack_like")
        if "shellfish" in (candidate.get("allergen_tags") or []) and not any(
            keyword in normalized_name
            for keyword in ["hat ", "dau ", "lac", "oc cho", "macca", "hanh nhan"]
        ):
            discouraged_reasons.append("shellfish_specialty")
        plant_based_prepared_protein = (
            self._is_plant_based_diet(dietary_preference)
            and any(keyword in normalized_name for keyword in ["dau phu", "dau hu", "tofu"])
            and not any(keyword in normalized_name for keyword in ["chien", "ran"])
        )
        if goal == "lose_weight" and protein >= 15 and fat >= 8 and "low_fat" not in diet_tags:
            if "fish" in allergen_tags and fat <= 12 and energy <= 260:
                preferred_reasons.append("healthy_fat_protein_support")
            elif plant_based_prepared_protein and fat <= 18 and energy <= 280:
                # Plain tofu is a practical plant protein even in weight-loss plans.
                preferred_reasons.append("plant_protein_acceptable_fat")
            else:
                discouraged_reasons.append("high_fat_protein_for_weight_loss")
        if fat >= 25 and energy >= 250 and not portion_safe_nut_name:
            discouraged_reasons.append("very_high_fat")
        if goal == "lose_weight" and portion_safe_nut_name and fat >= 18 and (fat >= 25 or energy >= 280):
            discouraged_reasons.append("seed_nut_heavy")
        if "produce" in diet_tags and not normalized_group.startswith("rau") and carbs < 15 and protein < 8:
            discouraged_reasons.append("weak_produce_anchor")
        if (
            produce_like
            and any(keyword in normalized_name for keyword in ["trai", "qua", "nho", "mit", "chuoi", "dau tay"])
            and protein < 6
        ):
            discouraged_reasons.append("fruit_only_support")
        if meal_readiness_tier == "blocked":
            hard_block_reasons.append("meal_ready_policy_blocked")
        elif meal_readiness_tier == "discouraged":
            discouraged_reasons.append("meal_ready_policy_discouraged")

        if any(keyword in normalized_name for keyword in PREFERRED_PROTEIN_KEYWORDS) or protein >= 20:
            preferred_reasons.append("good_protein_anchor")
        if any(keyword in normalized_name for keyword in PREFERRED_CARB_KEYWORDS) or carbs >= 35:
            preferred_reasons.append("good_carb_anchor")
        if "rau" in normalized_group or normalized_name.startswith(("rau ", "cai ")):
            preferred_reasons.append("good_produce_anchor")
        if goal == "lose_weight" and energy <= 220 and protein >= 15:
            preferred_reasons.append("weight_loss_friendly")
        if goal == "gain_muscle" and energy >= 140 and protein >= 15:
            preferred_reasons.append("muscle_gain_friendly")
        if "protein_anchor" in meal_role_tags and not (produce_like and not protein_like_name):
            preferred_reasons.append("meal_role_protein_anchor")
        if "carb_anchor" in meal_role_tags and not (produce_like and not carb_like_name and carbs < 30):
            preferred_reasons.append("meal_role_carb_anchor")
        if "produce_support" in meal_role_tags:
            preferred_reasons.append("meal_role_produce_support")

        return {
            "hard_block": bool(hard_block_reasons),
            "hard_block_reasons": hard_block_reasons,
            "discouraged_reasons": discouraged_reasons,
            "preferred_reasons": preferred_reasons,
            "normalized_name": normalized_name,
            "normalized_group": normalized_group,
            "energy_kcal": energy,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "meal_readiness_tier": meal_readiness_tier,
            "meal_role_tags": list(meal_role_tags),
            "planner_rank_weight": planner_rank_weight,
            "consumption_state": consumption_state,
            "final_output_allowed": final_output_allowed,
            "unsafe_output_reason": unsafe_output_reason,
        }
