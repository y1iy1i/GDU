from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .types import (
    AdapterStageResult,
    CheckpointName,
    CorrectionRequest,
    SourcePacket,
    TechnicalFailure,
)


class DeterministicClock:
    def __init__(self) -> None:
        self._tick = 0

    def now(self) -> str:
        self._tick += 1
        return f"2026-08-19T16:{self._tick // 60:02d}:{self._tick % 60:02d}+08:00"


class FixedUnderstandingAdapter:
    """A script-driven adapter for deterministic state-machine tests."""

    def __init__(
        self,
        proposals: Mapping[str, Sequence[Any]],
        revisions: Sequence[Any] = (),
    ) -> None:
        self._proposals = {
            stage: deque(responses) for stage, responses in proposals.items()
        }
        self._revisions = deque(revisions)
        self.call_trace: list[tuple[str, str, Any]] = []
        self.packet_trace: list[tuple[str, SourcePacket]] = []

    def propose(
        self,
        stage: CheckpointName,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        self.call_trace.append(("propose", stage, None))
        self.packet_trace.append((stage, source_packet))
        queue = self._proposals.get(stage)
        if not queue:
            raise TechnicalFailure(
                "fixed_adapter", f"no scripted response remained for {stage}"
            )
        return self._materialize(queue.popleft())

    def revise(
        self,
        request: CorrectionRequest,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        self.call_trace.append(("revise", request.target_checkpoint, request))
        self.packet_trace.append((request.target_checkpoint, source_packet))
        if not self._revisions:
            raise TechnicalFailure(
                "fixed_adapter", "no scripted revision response remained"
            )
        return self._materialize(self._revisions.popleft())

    @staticmethod
    def _materialize(value: Any) -> Any:
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value()
        return value
