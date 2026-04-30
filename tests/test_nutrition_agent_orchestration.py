import asyncio
import unittest
from unittest.mock import patch

from app.core.config import settings
from app.schemas.nutrition import NutritionAgentRecommendationRequest, NutritionRecommendationRequest
from app.services.nutrition.orchestration.graph import NutritionAgentGraph
from app.services.nutrition.orchestration.service import NutritionAgentService
from app.services.nutrition.orchestration.tools import NutritionCoreRecommendationTool


class FakeIntentParser:
    def __init__(self, clarification=None):
        self.clarification = clarification

    def get_chat_clarification(self, current_user, instruction):
        return self.clarification


class FakeCoreTool:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run(self, current_user, request):
        self.calls.append((current_user, request))
        return self.response


def safe_recommendation_response(validation=None, resolved_meals=None):
    return {
        "request_id": "core-request-1",
        "plan": {"summary": "Thực đơn tăng cơ đã được tạo.", "reasoning": [], "meals": []},
        "validation": validation
        or {
            "passed": True,
            "unsafe_raw_output_count": 0,
            "unsafe_label_count": 0,
            "totals": {"energy_kcal": 2200, "protein_g": 150, "carbs_g": 260, "fat_g": 60},
        },
        "resolved_meals": resolved_meals
        or [
            {
                "meal_name": "Bữa trưa",
                "items": [
                    {
                        "food_name": "Ức gà luộc",
                        "safe_display_name": "Ức gà luộc",
                        "final_output_allowed": True,
                        "consumption_state": "prepared_ready",
                    }
                ],
            }
        ],
    }


class NutritionAgentOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.previous_checkpoint = settings.NUTRITION_AGENT_REDIS_CHECKPOINT
        settings.NUTRITION_AGENT_REDIS_CHECKPOINT = False

    def tearDown(self):
        settings.NUTRITION_AGENT_REDIS_CHECKPOINT = self.previous_checkpoint

    def build_service(self, core_tool, intent_parser=None):
        graph = NutritionAgentGraph(
            core_tool=core_tool,
            intent_parser=intent_parser or FakeIntentParser(),
        )
        return NutritionAgentService(graph=graph)

    def test_agent_routes_recommendation_through_core_tool(self):
        core_tool = FakeCoreTool(safe_recommendation_response())
        service = self.build_service(core_tool)
        request = NutritionAgentRecommendationRequest(
            session_id="session-1",
            instruction="Tạo thực đơn tăng cơ",
        )

        result = service.run({"id": 1, "username": "demo"}, request)

        self.assertTrue(result["validation_passed"])
        self.assertIsNotNone(result["recommendation"])
        self.assertEqual(len(core_tool.calls), 1)
        self.assertIsInstance(core_tool.calls[0][1], NutritionRecommendationRequest)
        self.assertFalse(hasattr(core_tool.calls[0][1], "session_id"))
        self.assertEqual(
            [step["step"] for step in result["orchestration_trace"]],
            [
                "normalize_request",
                "clarify_intent",
                "run_core_recommendation",
                "inspect_validation",
                "generate_explanation",
                "finalize_response",
            ],
        )

    def test_agent_does_not_return_final_plan_when_validation_fails(self):
        response = safe_recommendation_response(
            validation={
                "passed": False,
                "unsafe_raw_output_count": 0,
                "unsafe_label_count": 0,
                "issues": [{"code": "macro_deviation"}],
            }
        )
        service = self.build_service(FakeCoreTool(response))

        result = service.run({"id": 1}, NutritionAgentRecommendationRequest(instruction="Ăn giảm mỡ"))

        self.assertFalse(result["validation_passed"])
        self.assertIsNone(result["recommendation"])
        self.assertEqual(result["status"], "needs_revision")
        self.assertIn("không trả final plan", result["answer"])

    def test_agent_blocks_unsafe_core_output_even_if_validation_flag_is_wrong(self):
        response = safe_recommendation_response(
            resolved_meals=[
                {
                    "meal_name": "Bữa trưa",
                    "items": [
                        {
                            "food_name": "Thịt gà tây, tươi",
                            "final_output_allowed": False,
                            "consumption_state": "requires_preparation",
                        }
                    ],
                }
            ]
        )
        service = self.build_service(FakeCoreTool(response))

        result = service.run({"id": 1}, NutritionAgentRecommendationRequest(instruction="Ăn tăng cơ"))

        self.assertFalse(result["validation_passed"])
        self.assertIsNone(result["recommendation"])
        self.assertEqual(result["status"], "needs_revision")

    def test_agent_clarification_short_circuits_core_tool(self):
        core_tool = FakeCoreTool(safe_recommendation_response())
        service = self.build_service(
            core_tool,
            intent_parser=FakeIntentParser({"question": "Bạn muốn tăng cơ hay giảm mỡ?"}),
        )

        result = service.run({"id": 1}, NutritionAgentRecommendationRequest(instruction="Tư vấn giúp tôi"))

        self.assertEqual(core_tool.calls, [])
        self.assertFalse(result["validation_passed"])
        self.assertIsNone(result["recommendation"])
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["answer"], "Bạn muốn tăng cơ hay giảm mỡ?")

    def test_shadow_endpoint_returns_agent_contract(self):
        from app.api.v3 import nutrition as nutrition_api

        fake_result = {
            "session_id": "session-1",
            "answer": "ok",
            "recommendation": None,
            "orchestration_trace": [],
            "engine": {"orchestrator": "langgraph"},
            "validation_passed": False,
            "status": "needs_clarification",
        }

        class FakeAgentService:
            def run(self, current_user, request):
                return fake_result

        with patch.object(nutrition_api, "nutrition_agent_service", FakeAgentService()):
            response = asyncio.run(
                nutrition_api.generate_nutrition_recommendation_agent(
                    NutritionAgentRecommendationRequest(instruction="demo"),
                    current_user={"id": 1},
                )
            )

        self.assertEqual(response["data"]["session_id"], "session-1")
        self.assertEqual(response["data"]["engine"]["orchestrator"], "langgraph")

    def test_langchain_tool_delegates_to_core_workflow(self):
        class FakeWorkflow:
            def __init__(self):
                self.calls = []

            def run_main_flow(self, current_user, request):
                self.calls.append((current_user, request))
                return safe_recommendation_response()

        workflow = FakeWorkflow()
        tool = NutritionCoreRecommendationTool(workflow=workflow).as_langchain_tool()

        result = tool.invoke(
            {
                "current_user": {"id": 1, "username": "demo"},
                "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
            }
        )

        self.assertEqual(result["request_id"], "core-request-1")
        self.assertEqual(len(workflow.calls), 1)
        self.assertEqual(workflow.calls[0][0]["id"], 1)
        self.assertIsInstance(workflow.calls[0][1], NutritionRecommendationRequest)


if __name__ == "__main__":
    unittest.main()
