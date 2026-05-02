import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.nutrition.knowledge.normalize import ascii_normalize
from app.services.ollama_nutrition_service import ollama_nutrition_service


logger = logging.getLogger(__name__)

NUTRITION_AGENT_ENDPOINT = "/api/v3/nutrition/recommendation-agent"

MEAL_PLAN_INTENT_MARKERS = (
    "tao thuc don",
    "lap thuc don",
    "goi y thuc don",
    "goi y mon",
    "recommend",
    "recommendation",
    "meal plan",
    "an gi",
    "hom nay an",
    "nen an",
    "mon an",
)


@dataclass(frozen=True)
class GeneralChatResult:
    answer: str
    engine: str
    status: str
    context_used: list[str] = field(default_factory=list)
    suggested_endpoint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "engine": self.engine,
            "status": self.status,
            "context_used": self.context_used,
            "suggested_endpoint": self.suggested_endpoint,
        }


class GeneralChatService:
    """Safe general chat layer that never creates final meal plans itself."""

    def __init__(self, llm_service=ollama_nutrition_service):
        self.llm_service = llm_service

    def answer(self, *, question: str, current_user: dict[str, Any] | None = None) -> GeneralChatResult:
        cleaned_question = " ".join((question or "").split())
        if not cleaned_question:
            return GeneralChatResult(
                answer="Bạn muốn hỏi gì về dinh dưỡng, tập luyện hoặc cách dùng app?",
                engine="GeneralChatService",
                status="needs_question",
            )

        if self._should_route_to_recommendation(cleaned_question):
            return self._recommendation_routing_answer()

        prompt = self._build_prompt(cleaned_question, current_user or {})
        try:
            raw_response = self.llm_service.generate_text(prompt, temperature=0.2)
            parsed = self.llm_service.parse_json(raw_response)
            answer = str(parsed.get("answer") or "").strip()
            if not answer:
                raise ValueError("LLM response did not include a usable answer.")
            return GeneralChatResult(
                answer=answer,
                engine=f"GeneralChatService+{getattr(self.llm_service, 'backend', 'llm')}",
                status="answered",
                context_used=self._clean_context(parsed.get("context_used")),
            )
        except Exception as exc:
            logger.warning("General chat LLM fallback used: %s", exc)
            return GeneralChatResult(
                answer=(
                    "Mình chưa gọi được model chat lúc này. Bạn vẫn có thể dùng "
                    f"`{NUTRITION_AGENT_ENDPOINT}` để tạo thực đơn an toàn, hoặc hỏi lại một câu ngắn hơn."
                ),
                engine="GeneralChatServiceFallback",
                status="fallback",
            )

    @staticmethod
    def _should_route_to_recommendation(question: str) -> bool:
        normalized = ascii_normalize(question)
        return any(marker in normalized for marker in MEAL_PLAN_INTENT_MARKERS)

    @staticmethod
    def _recommendation_routing_answer() -> GeneralChatResult:
        return GeneralChatResult(
            answer=(
                "Yêu cầu này cần engine recommendation để tính macro, lọc dị ứng/bệnh nền "
                "và kiểm tra an toàn món ăn. Frontend hãy gọi "
                f"`{NUTRITION_AGENT_ENDPOINT}` thay vì để chat tự tạo thực đơn."
            ),
            engine="GeneralChatRouter",
            status="use_nutrition_agent",
            context_used=["NutritionWorkflowService required"],
            suggested_endpoint=NUTRITION_AGENT_ENDPOINT,
        )

    @staticmethod
    def _build_prompt(question: str, current_user: dict[str, Any]) -> str:
        profile_hint = {
            "goal": current_user.get("target_goal"),
            "dietary_preference": current_user.get("dietary_preference"),
            "allergies": current_user.get("allergies"),
            "medical_conditions": current_user.get("medical_conditions"),
        }
        return f"""
You are a Vietnamese fitness nutrition assistant for general education.

Hard rules:
- Return ONLY a JSON object.
- Do not create a final meal plan, menu, shopping list, or specific meal items.
- Do not recommend raw/unsafe food.
- If the user asks for a personalized meal plan, say they must use the nutrition recommendation endpoint.
- Keep medical advice conservative and remind that serious disease requires a clinician.

User profile hint:
{profile_hint}

User question:
{question}

JSON schema:
{{
  "answer": "Vietnamese answer, concise but helpful",
  "context_used": ["short reason or context"]
}}
""".strip()

    @staticmethod
    def _clean_context(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item)[:120] for item in value if str(item).strip()][:5]


general_chat_service = GeneralChatService()
