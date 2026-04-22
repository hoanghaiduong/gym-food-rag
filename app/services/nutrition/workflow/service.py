"""Thin workflow facade.

The heavy runtime implementation lives in ``orchestrator.py`` so this module
can stay stable for imports while remaining small enough to maintain.
"""

from .orchestrator import NutritionWorkflowService, nutrition_workflow_service

__all__ = ["NutritionWorkflowService", "nutrition_workflow_service"]
