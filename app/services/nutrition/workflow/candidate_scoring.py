from __future__ import annotations

from .candidate_features import WorkflowCandidateFeaturesMixin
from .candidate_ranking import WorkflowCandidateRankingMixin
from .candidate_roles import WorkflowCandidateRolesMixin


class WorkflowCandidateScoringMixin(
    WorkflowCandidateRankingMixin,
    WorkflowCandidateRolesMixin,
    WorkflowCandidateFeaturesMixin,
):
    """Compatibility facade for candidate scoring helpers."""


__all__ = ["WorkflowCandidateScoringMixin"]
