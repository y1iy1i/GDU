from __future__ import annotations

from typing import Any, Iterable

from .types import Clock, RevisionRecord, StopGateResult


class BuildLogWriter:
    """Construct the four frozen Build Log v0 event types."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.events: list[dict[str, Any]] = []

    def checkpoint(
        self,
        name: str,
        outcome: str,
        summary: str,
        object_refs: Iterable[str] = (),
        trigger_evidence_refs: Iterable[str] = (),
    ) -> None:
        self._assert_open()
        event = self._base("checkpoint", name, object_refs, summary)
        event.update(
            {
                "checkpoint_name": name,
                "outcome": outcome,
                "result_summary": summary,
            }
        )
        refs = list(trigger_evidence_refs)
        if refs:
            event["trigger_evidence_refs"] = refs
        self.events.append(event)

    def revision(self, stage: str, record: RevisionRecord) -> None:
        self._assert_open()
        if not record.trigger_evidence_refs:
            raise ValueError("revision requires trigger evidence")
        if not record.affected_refs:
            raise ValueError("revision requires an affected object")
        event = self._base(
            "revision", stage, record.affected_refs, record.rationale
        )
        event.update(
            {
                "before_summary": record.before_summary,
                "after_summary": record.after_summary,
                "change_type": record.change_type,
                "trigger_evidence_refs": list(record.trigger_evidence_refs),
                "affected_refs": list(record.affected_refs),
                "surviving_alternative_refs": list(
                    record.surviving_alternative_refs
                ),
            }
        )
        self.events.append(event)

    def technical(
        self,
        stage: str,
        component: str,
        issue: str,
        resolution: str,
        outcome: str,
    ) -> None:
        self._assert_open()
        event = self._base("technical", stage, (), issue)
        event.update(
            {
                "component": component,
                "issue_summary": issue,
                "impact_summary": f"Builder stage {stage} was interrupted.",
                "resolution_summary": resolution,
                "outcome": outcome,
            }
        )
        self.events.append(event)

    def freeze(
        self, artifact_version: str, gate: StopGateResult
    ) -> None:
        self._assert_open()
        if not gate.passed:
            raise ValueError("cannot write freeze for a failed stop gate")
        event = self._base(
            "freeze",
            "cp6",
            (),
            "Coverage, evidence, and stability passed together.",
        )
        event.update(
            {
                "final_artifact_version": artifact_version,
                "stop_gate": {
                    "coverage": "passed",
                    "evidence": "passed",
                    "stability": "passed",
                },
                "artifacts_manifest_ref": "ARTIFACTS.sha256",
            }
        )
        self.events.append(event)

    def discard_unpublished_freeze(self) -> None:
        if self.events and self.events[-1]["event_type"] == "freeze":
            self.events.pop()

    def _assert_open(self) -> None:
        if self.events and self.events[-1]["event_type"] == "freeze":
            raise ValueError(
                "a frozen log is sealed; create a new artifact version instead"
            )

    def _base(
        self,
        event_type: str,
        stage: str,
        object_refs: Iterable[str],
        rationale: str,
    ) -> dict[str, Any]:
        logical_time = len(self.events) + 1
        return {
            "event_id": f"EV-{logical_time:03d}",
            "logical_time": logical_time,
            "timestamp": self._clock.now(),
            "event_type": event_type,
            "stage": stage,
            "object_refs": list(object_refs),
            "rationale": rationale or "No additional rationale supplied.",
        }
