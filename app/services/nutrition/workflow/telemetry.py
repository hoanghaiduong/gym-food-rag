from __future__ import annotations

from typing import Any, Optional

from .constants import utc_now
from .models import WorkflowTraceEntry


class WorkflowTelemetryMixin:
    def _trace_entry(
        self,
        step: str,
        status: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> WorkflowTraceEntry:
        timestamp = utc_now().isoformat()
        return {
            "step": step,
            "status": status,
            "started_at": timestamp,
            "ended_at": timestamp,
            "meta": meta or {},
        }

    def _record_step(
        self,
        workflow_state: dict[str, Any],
        step: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        workflow_state.setdefault("trace", []).append(self._trace_entry(step, "completed", meta))
        self.state_store.save_workflow_state(workflow_state["request_id"], workflow_state)
