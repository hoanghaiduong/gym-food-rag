from __future__ import annotations

from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest
from app.services.nutrition.knowledge.normalize import ascii_normalize


_EMPTY_PROFILE_VALUES = {"", "none", "null", "khong", "khong co", "no", "nope", "n/a", "na"}

_ALLERGY_CONFIRMATION_PHRASES = (
    "khong di ung",
    "khong co di ung",
    "khong bi di ung",
    "khong gap di ung",
    "khong di ung gi",
    "khong di ung thuc pham",
    "no allergies",
    "no food allergy",
    "no food allergies",
)

_ALLERGY_RESTRICTION_MARKERS = (
    "di ung",
    "khong an",
    "khong dung nap",
    "khong hop",
    "tranh",
    "kieng",
    "avoid",
    "allergy",
    "allergic",
)

_MEDICAL_CONFIRMATION_PHRASES = (
    "khong benh nen",
    "khong co benh nen",
    "khong mac benh nen",
    "khong bi benh nen",
    "khong co tien su benh",
    "suc khoe binh thuong",
    "no medical condition",
    "no medical conditions",
    "no underlying condition",
    "no underlying conditions",
)

_MEDICAL_CONDITION_MARKERS = (
    "benh nen",
    "tieu duong",
    "dai thao duong",
    "huyet ap",
    "tang huyet ap",
    "tim mach",
    "benh tim",
    "than",
    "suy than",
    "gan",
    "gout",
    "gut",
    "mo mau",
    "cholesterol",
    "da day",
    "tieu hoa",
    "diabetes",
    "hypertension",
    "kidney",
    "heart disease",
    "gout",
)

_PROFILE_ALLERGY_FIELDS = ("allergy_tags", "allergies")
_PROFILE_MEDICAL_FIELDS = (
    "medical_conditions",
    "medical_condition",
    "health_conditions",
    "health_condition",
    "underlying_conditions",
    "diseases",
)


class NutritionAgentSafetyClarificationPolicy:
    """Builds deterministic safety clarifications before recommendation planning."""

    def build(
        self,
        current_user: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> dict[str, Any] | None:
        instruction = ascii_normalize(request.instruction or "")
        missing_fields = self._missing_safety_fields(current_user, request, instruction)
        if not missing_fields:
            return None

        return {
            "needed": True,
            "reason": "missing_safety_profile",
            "required_fields": missing_fields,
            "question": self._build_question(missing_fields),
        }

    def _missing_safety_fields(
        self,
        current_user: dict[str, Any],
        request: NutritionRecommendationRequest,
        instruction: str,
    ) -> list[str]:
        missing: list[str] = []
        if not self._allergy_status_known(current_user, request, instruction):
            missing.append("allergies")
        if not self._medical_status_known(current_user, instruction):
            missing.append("medical_conditions")
        return missing

    def _allergy_status_known(
        self,
        current_user: dict[str, Any],
        request: NutritionRecommendationRequest,
        instruction: str,
    ) -> bool:
        if self._profile_has_value(current_user, _PROFILE_ALLERGY_FIELDS):
            return True
        if request.excluded_foods:
            return True
        if any(phrase in instruction for phrase in _ALLERGY_CONFIRMATION_PHRASES):
            return True
        return any(marker in instruction for marker in _ALLERGY_RESTRICTION_MARKERS)

    def _medical_status_known(self, current_user: dict[str, Any], instruction: str) -> bool:
        if self._profile_has_value(current_user, _PROFILE_MEDICAL_FIELDS):
            return True
        if any(phrase in instruction for phrase in _MEDICAL_CONFIRMATION_PHRASES):
            return True
        return any(marker in instruction for marker in _MEDICAL_CONDITION_MARKERS)

    def _profile_has_value(self, current_user: dict[str, Any], fields: tuple[str, ...]) -> bool:
        for field in fields:
            value = current_user.get(field)
            if isinstance(value, list):
                if any(str(item).strip() for item in value):
                    return True
                continue
            normalized = ascii_normalize(str(value or ""))
            if normalized and normalized not in _EMPTY_PROFILE_VALUES:
                return True
        return False

    def _build_question(self, missing_fields: list[str]) -> str:
        if missing_fields == ["allergies"]:
            return (
                "Trước khi tạo thực đơn, bạn có dị ứng hoặc cần kiêng thực phẩm nào không, "
                "đặc biệt là hải sản như cá, tôm, cua, mực, ốc? Nếu không có, hãy trả lời: "
                "\"Không dị ứng\"."
            )
        if missing_fields == ["medical_conditions"]:
            return (
                "Trước khi tạo thực đơn, bạn có bệnh nền hoặc vấn đề sức khỏe nào cần lưu ý "
                "như tiểu đường, huyết áp, gout, bệnh thận, gan, tim mạch không? Nếu không có, "
                "hãy trả lời: \"Không bệnh nền\"."
            )
        return (
            "Trước khi tạo thực đơn, bạn cho mình biết thêm 2 ý an toàn nhé: bạn có bệnh nền "
            "hoặc vấn đề sức khỏe nào như tiểu đường, huyết áp, gout, bệnh thận/tim mạch không; "
            "và bạn có dị ứng hoặc cần kiêng hải sản như cá, tôm, cua, mực, ốc hay thực phẩm nào "
            "khác không? Nếu không có, chỉ cần trả lời: \"Không bệnh nền, không dị ứng\"."
        )
