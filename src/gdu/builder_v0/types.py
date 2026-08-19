from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence


CheckpointName = Literal["cp1", "cp2", "cp3", "cp4", "cp5", "cp6"]
RunOutcome = Literal[
    "frozen_complete",
    "provisional_complete",
    "input_rejected",
    "technical_failed",
]


class TechnicalFailure(RuntimeError):
    """A transport, I/O, parse, or other non-semantic failure."""

    def __init__(self, component: str, summary: str) -> None:
        super().__init__(summary)
        self.component = component
        self.summary = summary


class CandidateValidationError(ValueError):
    """A parseable candidate that violates the public candidate contract."""


@dataclass(frozen=True)
class SourceRequest:
    purpose: str
    page_ranges: tuple[tuple[int, int], ...]
    modalities: tuple[str, ...] = ("text",)
    locator_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfPageFragment:
    page: int
    locator: str
    excerpt: str
    fragment_sha256: str

    def as_evidence_fragment(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "locator": self.locator,
            "excerpt": self.excerpt,
            "fragment_sha256": self.fragment_sha256,
        }


@dataclass(frozen=True)
class SourcePacket:
    source_document_id: str
    request_identity: str
    pdf_fragments: tuple[PdfPageFragment, ...]
    navigation_text: tuple[str, ...] = ()
    retrieval_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceDocumentIdentity:
    document_id: str
    original_filename: str
    source_sha256: str
    pdf_page_count: int
    extraction_system: str


@dataclass(frozen=True)
class BuilderRunSpec:
    run_id: str
    source_pdf: Path
    extracted_text: Path
    gdu_schema: Path
    gdu_schema_sha256: str
    build_log_schema: Path
    build_log_schema_sha256: str
    protocol_path: Path
    protocol_name: str
    protocol_version: str
    protocol_sha256: str
    config_or_prompt_sha256: str
    model_id: str
    reasoning_effort: str
    output_dir: Path
    expected_source_sha256: str | None = None
    expected_extracted_text_sha256: str | None = None
    checkpoint_source_requests: Mapping[str, SourceRequest] = field(
        default_factory=dict
    )
    max_semantic_corrections: int = 2
    max_technical_retries: int = 1
    single_builder: bool = True
    external_knowledge_allowed: bool = False

    @property
    def immutable_run_identity(self) -> tuple[str, str, str]:
        return (
            self.model_id,
            self.reasoning_effort,
            self.config_or_prompt_sha256,
        )


@dataclass(frozen=True)
class Gap:
    gap_id: str
    gate_dimension: Literal["coverage", "evidence", "stability"]
    check_kind: Literal[
        "ordinary", "cross_carrier", "cross_section", "negative_boundary"
    ]
    affected_refs: tuple[str, ...]
    source_scope: tuple[tuple[int, int], ...]
    reason: str
    earliest_checkpoint: Literal["cp1", "cp2", "cp3", "cp4", "cp5"]
    requested_action: str


@dataclass(frozen=True)
class StopGateResult:
    coverage: Literal["passed", "failed"]
    evidence: Literal["passed", "failed"]
    stability: Literal["passed", "failed"]
    cross_carrier: Literal["passed", "failed"]
    cross_section: Literal["passed", "failed"]
    negative_boundary: Literal["passed", "failed"]
    gaps: tuple[Gap, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        values = (
            self.coverage,
            self.evidence,
            self.stability,
            self.cross_carrier,
            self.cross_section,
            self.negative_boundary,
        )
        fully_passed = all(value == "passed" for value in values)
        if fully_passed and self.gaps:
            raise ValueError("a fully passed stop gate cannot contain gaps")
        if not fully_passed and not self.gaps:
            raise ValueError("a failed stop gate must contain a concrete gap")

    @property
    def passed(self) -> bool:
        return all(
            value == "passed"
            for value in (
                self.coverage,
                self.evidence,
                self.stability,
                self.cross_carrier,
                self.cross_section,
                self.negative_boundary,
            )
        )


@dataclass(frozen=True)
class CandidateObject:
    kind: Literal[
        "physical_structure",
        "semantic_unit",
        "assertion",
        "interpretation_group",
        "relation",
        "evidence",
    ]
    handle: str
    fields: Mapping[str, Any]
    source_authority: Literal["pdf", "navigation"] = "pdf"


@dataclass(frozen=True)
class ObjectMutation:
    operation: Literal["replace", "downgrade", "withdraw"]
    target_ref: str
    replacement_fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateBundle:
    stage: CheckpointName
    objects: tuple[CandidateObject, ...] = ()
    manifest: Mapping[str, Any] | None = None
    generative_plan: Mapping[str, Any] | None = None
    mutations: tuple[ObjectMutation, ...] = ()


@dataclass(frozen=True)
class RevisionRecord:
    before_summary: str
    after_summary: str
    change_type: Literal[
        "promote",
        "replace",
        "downgrade",
        "retain_alternative",
        "withdraw",
    ]
    trigger_evidence_refs: tuple[str, ...]
    affected_refs: tuple[str, ...]
    surviving_alternative_refs: tuple[str, ...] = ()
    rationale: str = "Evidence-triggered public revision."


@dataclass(frozen=True)
class AdapterStageResult:
    stage: CheckpointName
    bundle: CandidateBundle | None = None
    stop_gate: StopGateResult | None = None
    result_summary: str = "Stage completed."
    revisions: tuple[RevisionRecord, ...] = ()
    observed_run_identity: tuple[str, str, str] | None = None


@dataclass(frozen=True)
class CorrectionRequest:
    correction_round: int
    target_checkpoint: Literal["cp1", "cp2", "cp3", "cp4", "cp5"]
    target_refs: tuple[str, ...]
    source_scope: tuple[tuple[int, int], ...]
    gaps: tuple[Gap, ...]
    immutable_run_identity: tuple[str, str, str]


@dataclass
class WorkingGDU:
    data: dict[str, Any] = field(
        default_factory=lambda: {
            "physical_structure": [],
            "semantic_units": [],
            "assertions": {"items": [], "interpretation_groups": []},
            "relations": [],
            "evidence": [],
        }
    )
    completed_checkpoints: list[str] = field(default_factory=list)
    open_gaps: list[Gap] = field(default_factory=list)

    def public_view(self) -> Mapping[str, Any]:
        # Adapters receive an isolated snapshot, never the mutable Builder state.
        return copy.deepcopy(self.data)


@dataclass(frozen=True)
class BuilderRunResult:
    outcome: RunOutcome
    artifact_paths: tuple[Path, ...]
    semantic_corrections_used: int
    technical_retries_used: int
    final_checkpoint: str
    public_summary: str
    state_trace: tuple[str, ...]


class UnderstandingAdapter(Protocol):
    def propose(
        self,
        stage: CheckpointName,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        ...

    def revise(
        self,
        request: CorrectionRequest,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        ...


class Clock(Protocol):
    def now(self) -> str:
        ...


class PdfBackend(Protocol):
    @property
    def name(self) -> str:
        ...

    def page_count(self, path: Path) -> int:
        ...

    def extract_page_text(self, path: Path, page_number: int) -> str:
        ...
