from typing import Any

from app.services.nutrition_intent_service import nutrition_intent_service
from app.services.nutrition_knowledge_service import canonical_knowledge_service
from app.services.ollama_nutrition_service import ollama_nutrition_service
from app.services.redis_state_service import redis_state_service

from .candidate_diagnostics import WorkflowCandidateDiagnosticsMixin
from .candidate_pool import WorkflowCandidatePoolMixin
from .candidate_pool_support import WorkflowCandidatePoolSupportMixin
from .candidate_scoring import WorkflowCandidateScoringMixin
from .explanations import WorkflowExplanationsMixin
from .generation import WorkflowGenerationMixin
from .meal_realism import WorkflowMealRealismMixin
from .planning import WorkflowPlanningMixin
from .profile_targets import WorkflowProfileTargetsMixin
from .prompts import WorkflowPromptsMixin
from .resolution import WorkflowResolutionMixin
from .response_runtime import WorkflowResponseRuntimeMixin
from .retrieval_context import WorkflowRetrievalContextMixin
from .retrieval_queries import WorkflowRetrievalQueriesMixin
from .retrieval_support_queries import WorkflowRetrievalSupportQueriesMixin
from .retrieval_stage import WorkflowRetrievalStageMixin
from .runtime import WorkflowRuntimeMixin
from .telemetry import WorkflowTelemetryMixin
from .validation import WorkflowValidationMixin


class NutritionWorkflowService(
    WorkflowCandidateDiagnosticsMixin,
    WorkflowRetrievalStageMixin,
    WorkflowCandidatePoolSupportMixin,
    WorkflowCandidatePoolMixin,
    WorkflowRetrievalQueriesMixin,
    WorkflowRetrievalSupportQueriesMixin,
    WorkflowRetrievalContextMixin,
    WorkflowCandidateScoringMixin,
    WorkflowMealRealismMixin,
    WorkflowExplanationsMixin,
    WorkflowGenerationMixin,
    WorkflowPromptsMixin,
    WorkflowResolutionMixin,
    WorkflowResponseRuntimeMixin,
    WorkflowTelemetryMixin,
    WorkflowRuntimeMixin,
    WorkflowProfileTargetsMixin,
    WorkflowPlanningMixin,
    WorkflowValidationMixin,
):
    def __init__(self):
        self.knowledge = canonical_knowledge_service
        self.intent_parser = nutrition_intent_service
        self.llm = ollama_nutrition_service
        self.state_store = redis_state_service
        self._llm_retrieval_rewrite_enabled_override = None
        self._retrieval_instruction_rewrite_cache: dict[tuple[str, ...], str] = {}
        self._retrieval_query_bundle_cache: dict[tuple[str, ...], list[dict[str, Any]]] = {}


nutrition_workflow_service = NutritionWorkflowService()
