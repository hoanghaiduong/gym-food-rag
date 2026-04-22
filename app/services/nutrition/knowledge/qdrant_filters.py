from __future__ import annotations

from typing import Iterable, Optional

try:
    from qdrant_client.http import models
except ModuleNotFoundError:  # pragma: no cover
    models = None

from .normalize import ascii_normalize


class QdrantFilterMixin:
    def _build_filter(
        self,
        dietary_preference: Optional[str],
        allergy_tags: Iterable[str],
        entity_types: Optional[Iterable[str]],
        expected_role_tags: Optional[Iterable[str]] = None,  # New: hard filter for precision/recall
    ):
        """Extended to support expected_role_tags as MUST conditions.
        This is the key to boosting precision@10 and exact recall by constraining search space early."""
        must = []
        must_not = []

        must.append(models.FieldCondition(key="retrieval_enabled", match=models.MatchValue(value=True)))
        must.append(models.FieldCondition(key="production_retrieval_enabled", match=models.MatchValue(value=True)))

        entity_type_values = [item for item in (entity_types or []) if item]
        if entity_type_values:
            must.append(models.FieldCondition(key="entity_type", match=models.MatchAny(any=entity_type_values)))

        preference = ascii_normalize(dietary_preference)
        if preference == "vegetarian":
            must.append(models.FieldCondition(key="diet_tags", match=models.MatchAny(any=["vegetarian", "vegan"])))
        elif preference == "vegan":
            must.append(models.FieldCondition(key="diet_tags", match=models.MatchAny(any=["vegan"])))
        elif preference == "pescatarian":
            must.append(models.FieldCondition(key="diet_tags", match=models.MatchAny(any=["pescatarian", "vegetarian", "vegan"])))

        allergy_values = [tag for tag in allergy_tags if tag]
        if allergy_values:
            must_not.append(models.FieldCondition(key="allergen_tags", match=models.MatchAny(any=allergy_values)))

        # NEW: Hard filter on expected roles (protein_anchor, produce_support, post_workout_friendly...)
        # This directly addresses low precision (too many irrelevant snacks) and low recall (missed anchors)
        if expected_role_tags:
            role_values = [tag for tag in expected_role_tags if tag]
            if role_values:
                must.append(models.FieldCondition(
                    key="meal_role_tags",
                    match=models.MatchAny(any=role_values)
                ))

        if not must and not must_not:
            return None
        return models.Filter(must=must or None, must_not=must_not or None)
