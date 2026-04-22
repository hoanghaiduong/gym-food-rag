from __future__ import annotations

from .validation_metrics import WorkflowValidationMetricsMixin
from .validation_policy import WorkflowValidationPolicyMixin


class WorkflowValidationMixin(
    WorkflowValidationPolicyMixin,
    WorkflowValidationMetricsMixin,
):
    """Compatibility facade for validation helpers."""


__all__ = ["WorkflowValidationMixin"]
