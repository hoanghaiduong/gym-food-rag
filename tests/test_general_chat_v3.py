import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import BackgroundTasks

from app.api.v3 import chat_v3 as chat_api
from app.schemas.chat import ChatRequest
from app.services.general_chat_service import GeneralChatService, NUTRITION_AGENT_ENDPOINT


class FakeLlmService:
    backend = "fake"

    def __init__(self):
        self.calls = []

    def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        self.calls.append((prompt, temperature))
        return json.dumps(
            {
                "answer": "TDEE la tong nang luong co the ban tieu hao trong mot ngay.",
                "context_used": ["general nutrition education"],
            }
        )

    def parse_json(self, raw_text: str):
        return json.loads(raw_text)


class FakeHistoryService:
    def __init__(self, db_session):
        self.db_session = db_session

    def create_session(self, user_id: int, first_question: str):
        return "session-1"

    def get_session_messages(self, session_id: str, user_id: int):
        return []

    async def save_interaction(self, **kwargs):
        return None


class GeneralChatV3Tests(unittest.TestCase):
    def test_general_question_uses_llm_and_returns_answer(self):
        llm = FakeLlmService()
        service = GeneralChatService(llm_service=llm)

        result = service.answer(question="TDEE la gi?", current_user={"id": 1})

        self.assertEqual(result.status, "answered")
        self.assertIn("TDEE", result.answer)
        self.assertEqual(len(llm.calls), 1)

    def test_meal_plan_question_routes_to_recommendation_agent_without_llm(self):
        llm = FakeLlmService()
        service = GeneralChatService(llm_service=llm)

        result = service.answer(question="Tao thuc don tang co 3 bua", current_user={"id": 1})

        self.assertEqual(result.status, "use_nutrition_agent")
        self.assertEqual(result.suggested_endpoint, NUTRITION_AGENT_ENDPOINT)
        self.assertEqual(llm.calls, [])

    def test_general_goal_question_does_not_route_without_meal_plan_request(self):
        llm = FakeLlmService()
        service = GeneralChatService(llm_service=llm)

        result = service.answer(question="Tang co can bao nhieu protein?", current_user={"id": 1})

        self.assertEqual(result.status, "answered")
        self.assertEqual(len(llm.calls), 1)

    def test_chat_endpoint_returns_safe_routing_contract(self):
        with patch.object(chat_api, "HistoryService", FakeHistoryService):
            response = asyncio.run(
                chat_api.chat_v3(
                    ChatRequest(question="Goi y thuc don tang co"),
                    BackgroundTasks(),
                    current_user={"id": 1, "target_goal": "gain_muscle"},
                    db=None,
                )
            )

        data = response["data"]
        self.assertEqual(data["session_id"], "session-1")
        self.assertEqual(data["status"], "use_nutrition_agent")
        self.assertEqual(data["suggested_endpoint"], NUTRITION_AGENT_ENDPOINT)


if __name__ == "__main__":
    unittest.main()
