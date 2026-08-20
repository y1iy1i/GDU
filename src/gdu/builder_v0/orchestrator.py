from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

from .artifact_writer import ArtifactWriterValidator
from .id_allocator import CanonicalIdAllocator
from .log_writer import BuildLogWriter
from .source_reader import SourceReader
from .types import (
    AdapterStageResult,
    BuilderRunResult,
    BuilderRunSpec,
    CandidateBundle,
    CandidateValidationError,
    CorrectionRequest,
    Gap,
    StopGateResult,
    SourcePacket,
    SourceRequest,
    TechnicalFailure,
    UnderstandingAdapter,
    WorkingGDU,
)


T = TypeVar("T")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
CHECKPOINTS = ("cp1", "cp2", "cp3", "cp4", "cp5")
CHECKPOINT_RANK = {name: index for index, name in enumerate(CHECKPOINTS)}


class BuilderOrchestrator:
    """A deterministic orchestration skeleton with no model dependency."""

    def __init__(
        self,
        spec: BuilderRunSpec,
        adapter: UnderstandingAdapter,
        clock: Any,
        source_reader: SourceReader | None = None,
        navigation_text: Mapping[int, str] | None = None,
        artifact_writer: ArtifactWriterValidator | None = None,
    ) -> None:
        self.spec = spec
        self.adapter = adapter
        self.clock = clock
        self.source_reader = source_reader
        self.source_identity = None
        self.navigation_text = navigation_text or {}
        self.source_plan = copy.deepcopy(dict(spec.checkpoint_source_requests))
        self.log = BuildLogWriter(clock)
        self.ids = CanonicalIdAllocator()
        self.writer = artifact_writer or ArtifactWriterValidator(
            spec.gdu_schema, spec.build_log_schema
        )
        self.working = WorkingGDU()
        self.semantic_corrections_used = 0
        self.technical_retries_used = 0
        self.state_trace: list[str] = ["initialized"]
        self.final_checkpoint = "initialized"

    def build(self) -> BuilderRunResult:
        input_error = self._verify_inputs()
        if input_error:
            return self._result("input_rejected", (), "input", input_error)
        self.state_trace.append("input_verified")

        try:
            for stage in CHECKPOINTS:
                source_packet = self._source_packet(
                    stage, self.source_plan[stage]
                )
                result, promoted = self._invoke_candidate_stage(
                    stage,
                    lambda stage=stage, source_packet=source_packet: self.adapter.propose(
                        stage, source_packet, self.working.public_view()
                    ),
                    source_packet=source_packet,
                )
                self.working.completed_checkpoints.append(stage)
                self.final_checkpoint = stage
                self.state_trace.append(f"{stage}_complete")
                self.log.checkpoint(
                    stage,
                    "completed",
                    result.result_summary,
                    promoted,
                )

            while True:
                cp6_packet = self._source_packet(
                    "cp6", self.source_plan["cp6"]
                )
                cp6 = self._invoke_stage(
                    "cp6",
                    lambda cp6_packet=cp6_packet: self.adapter.propose(
                        "cp6", cp6_packet, self.working.public_view()
                    ),
                )
                gate = cp6.stop_gate
                if gate is None:
                    raise TechnicalFailure(
                        "understanding_adapter", "cp6 did not return a stop gate"
                    )
                self.final_checkpoint = "cp6"
                outcome = "passed" if gate.passed else "failed"
                self.log.checkpoint("cp6", outcome, gate.summary or outcome)
                self.state_trace.append(f"cp6_{outcome}")

                if gate.passed:
                    return self._finalize("frozen", gate)

                self.working.open_gaps = list(gate.gaps)
                if self.semantic_corrections_used >= self.spec.max_semantic_corrections:
                    return self._finalize("provisional", gate)

                self.semantic_corrections_used += 1
                request = self._plan_correction(gate)
                correction_source_request = SourceRequest(
                    purpose=(
                        f"bounded correction {request.correction_round} for "
                        f"{request.target_checkpoint}"
                    ),
                    page_ranges=request.source_scope,
                    modalities=("text",),
                    locator_hints=request.target_refs,
                )
                correction_packet = self._source_packet(
                    request.target_checkpoint, correction_source_request
                )
                revision_result, promoted = self._invoke_candidate_stage(
                    request.target_checkpoint,
                    lambda request=request, correction_packet=correction_packet: self.adapter.revise(
                        request, correction_packet, self.working.public_view()
                    ),
                    correction_request=request,
                    source_packet=correction_packet,
                )
                for revision in revision_result.revisions:
                    self.log.revision(request.target_checkpoint, revision)
                self.log.checkpoint(
                    request.target_checkpoint,
                    "completed",
                    revision_result.result_summary,
                    promoted,
                )
                self.state_trace.append(
                    f"correction_{self.semantic_corrections_used}_{request.target_checkpoint}"
                )
        except TechnicalFailure as exc:
            self.state_trace.append("technical_failed")
            snapshot_paths = (
                ()
                if exc.component in {"artifact_writer", "artifact_validator"}
                else self._preserve_complete_snapshot()
            )
            return self._result(
                "technical_failed",
                snapshot_paths,
                self.final_checkpoint,
                f"{exc.component}: {exc.summary}",
            )

    def _accept_stage_result(
        self,
        expected_stage: str,
        result: AdapterStageResult,
        correction_request: CorrectionRequest | None = None,
    ) -> tuple[str, ...]:
        if result.stage != expected_stage:
            raise TechnicalFailure(
                "understanding_adapter",
                f"expected {expected_stage}, received {result.stage}",
            )
        if expected_stage == "cp6" and result.stop_gate is None:
            raise TechnicalFailure(
                "understanding_adapter", "cp6 response is missing stop_gate"
            )
        if expected_stage != "cp6" and result.stop_gate is not None:
            raise TechnicalFailure(
                "understanding_adapter", "stop_gate is only valid at cp6"
            )
        if (
            result.observed_run_identity is not None
            and result.observed_run_identity != self.spec.immutable_run_identity
        ):
            raise TechnicalFailure(
                "policy_guard", "adapter attempted to change immutable run identity"
            )
        if result.bundle is None:
            return ()
        if result.bundle.stage != expected_stage:
            raise TechnicalFailure(
                "understanding_adapter", "candidate bundle stage mismatch"
            )
        if correction_request is None and result.bundle.mutations:
            raise CandidateValidationError(
                "object mutations are only allowed during a bounded correction"
            )
        self._validate_revision_contract(result, correction_request)
        return self._promote(result.bundle, correction_request)

    def _promote(
        self,
        bundle: CandidateBundle,
        correction_request: CorrectionRequest | None = None,
    ) -> tuple[str, ...]:
        self._validate_correction_scope(bundle, correction_request)
        draft = copy.deepcopy(self.working.data)
        promoted: list[str] = []
        if bundle.manifest is not None:
            draft["manifest"] = copy.deepcopy(dict(bundle.manifest))
        if bundle.generative_plan is not None:
            draft["generative_plan"] = copy.deepcopy(dict(bundle.generative_plan))
        for mutation in bundle.mutations:
            self._apply_mutation(draft, mutation)
        canonical = self.ids.canonicalize(bundle)
        for kind, value in canonical:
            promoted.append(value["id"])
            if kind == "physical_structure":
                draft["physical_structure"].append(value)
            elif kind == "semantic_unit":
                draft["semantic_units"].append(value)
            elif kind == "assertion":
                draft["assertions"]["items"].append(value)
            elif kind == "interpretation_group":
                draft["assertions"]["interpretation_groups"].append(value)
            elif kind == "relation":
                draft["relations"].append(value)
            elif kind == "evidence":
                draft["evidence"].append(value)
        self.working.data = draft
        return tuple(promoted)

    def _validate_revision_contract(
        self,
        result: AdapterStageResult,
        request: CorrectionRequest | None,
    ) -> None:
        for revision in result.revisions:
            if not revision.trigger_evidence_refs or not revision.affected_refs:
                raise CandidateValidationError(
                    "revision requires trigger evidence and affected refs"
                )
        if request is not None and result.bundle is not None and result.bundle.mutations:
            changed = {mutation.target_ref for mutation in result.bundle.mutations}
            documented = {
                ref for revision in result.revisions for ref in revision.affected_refs
            }
            if not changed.issubset(documented):
                raise CandidateValidationError(
                    "every object mutation must be covered by a revision record"
                )

    def _validate_correction_scope(
        self,
        bundle: CandidateBundle,
        request: CorrectionRequest | None,
    ) -> None:
        if request is None:
            return
        allowed_refs = set(request.target_refs)
        for mutation in bundle.mutations:
            if mutation.target_ref not in allowed_refs:
                raise TechnicalFailure(
                    "policy_guard",
                    f"correction attempted out-of-scope target {mutation.target_ref}",
                )
        for candidate in bundle.objects:
            if candidate.kind != "evidence":
                continue
            for fragment in candidate.fields.get("fragments", []):
                page = fragment.get("page")
                if page is not None and not any(
                    start <= page <= end for start, end in request.source_scope
                ):
                    raise TechnicalFailure(
                        "policy_guard",
                        f"correction requested out-of-scope evidence page {page}",
                    )

    def _apply_mutation(self, draft: dict[str, Any], mutation: Any) -> None:
        located = self._locate_object(draft, mutation.target_ref)
        if located is None:
            raise CandidateValidationError(
                f"mutation target does not exist: {mutation.target_ref}"
            )
        container, index = located
        current = container[index]
        if mutation.operation == "replace":
            if "id" in mutation.replacement_fields:
                raise CandidateValidationError("a replacement cannot change canonical id")
            replacement = copy.deepcopy(current)
            replacement.update(copy.deepcopy(dict(mutation.replacement_fields)))
            replacement["id"] = mutation.target_ref
            container[index] = replacement
        elif mutation.operation == "downgrade":
            if "assessment_complete" not in current:
                raise CandidateValidationError(
                    "only assessed assertions or relations can be downgraded"
                )
            replacement = copy.deepcopy(current)
            replacement.update(copy.deepcopy(dict(mutation.replacement_fields)))
            replacement["assessment_complete"] = False
            replacement.pop("evidence_status", None)
            container[index] = replacement
        elif mutation.operation == "withdraw":
            container.pop(index)
            if self._contains_reference(draft, mutation.target_ref):
                raise CandidateValidationError(
                    "withdrawn object is still referenced by another object"
                )
        else:
            raise CandidateValidationError(
                f"unsupported mutation operation: {mutation.operation}"
            )

    @staticmethod
    def _locate_object(
        data: Mapping[str, Any], target_ref: str
    ) -> tuple[list[dict[str, Any]], int] | None:
        containers = (
            data.get("physical_structure", []),
            data.get("semantic_units", []),
            data.get("assertions", {}).get("items", []),
            data.get("assertions", {}).get("interpretation_groups", []),
            data.get("relations", []),
            data.get("evidence", []),
        )
        for container in containers:
            for index, item in enumerate(container):
                if item.get("id") == target_ref:
                    return container, index
        return None

    @classmethod
    def _contains_reference(cls, value: Any, target_ref: str) -> bool:
        if isinstance(value, dict):
            return any(
                key != "id" and cls._contains_reference(item, target_ref)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(cls._contains_reference(item, target_ref) for item in value)
        return value == target_ref

    def _invoke_stage(
        self, stage: str, call: Callable[[], AdapterStageResult]
    ) -> AdapterStageResult:
        def checked_call() -> AdapterStageResult:
            result = call()
            if not isinstance(result, AdapterStageResult):
                raise TechnicalFailure(
                    "understanding_adapter", "malformed structured response"
                )
            if (
                result.observed_run_identity is not None
                and result.observed_run_identity != self.spec.immutable_run_identity
            ):
                raise TechnicalFailure(
                    "policy_guard",
                    "adapter attempted to change immutable run identity",
                )
            return result

        return self._invoke_technical(stage, "understanding_adapter", checked_call)

    def _invoke_candidate_stage(
        self,
        stage: str,
        call: Callable[[], AdapterStageResult],
        correction_request: CorrectionRequest | None = None,
        source_packet: SourcePacket | None = None,
    ) -> tuple[AdapterStageResult, tuple[str, ...]]:
        def checked_and_promoted() -> tuple[AdapterStageResult, tuple[str, ...]]:
            result = call()
            if not isinstance(result, AdapterStageResult):
                raise TechnicalFailure(
                    "understanding_adapter", "malformed structured response"
                )
            try:
                if result.bundle is not None and source_packet is not None:
                    self._validate_evidence_against_packet(
                        result.bundle, source_packet
                    )
                promoted = self._accept_stage_result(
                    stage, result, correction_request
                )
            except CandidateValidationError as exc:
                raise TechnicalFailure(
                    "understanding_adapter", f"invalid candidate bundle: {exc}"
                ) from exc
            return result, promoted

        return self._invoke_technical(
            stage, "candidate_promotion", checked_and_promoted
        )

    def _source_packet(
        self, stage: str, request: SourceRequest
    ) -> SourcePacket:
        if self.source_reader is None:
            raise TechnicalFailure(
                "source_reader", "Builder requires an injected SourceReader"
            )
        def read_packet() -> SourcePacket:
            try:
                return self.source_reader.read(request, self.navigation_text)
            except (ValueError, OSError, IndexError) as exc:
                raise TechnicalFailure("source_reader", str(exc)) from exc

        return self._invoke_technical(stage, "source_reader", read_packet)

    @staticmethod
    def _validate_evidence_against_packet(
        bundle: CandidateBundle, packet: SourcePacket
    ) -> None:
        authoritative = {
            fragment.page: fragment.excerpt for fragment in packet.pdf_fragments
        }
        for candidate in bundle.objects:
            if candidate.kind != "evidence":
                continue
            for fragment in candidate.fields.get("fragments", []):
                page = fragment.get("page")
                excerpt = " ".join(str(fragment.get("excerpt", "")).split())
                page_text = authoritative.get(page, "")
                if not excerpt or excerpt not in page_text:
                    raise CandidateValidationError(
                        "candidate evidence is absent from the authorized PDF packet"
                    )
                expected_hash = hashlib.sha256(
                    str(fragment.get("excerpt", "")).encode("utf-8")
                ).hexdigest()
                if fragment.get("fragment_sha256") != expected_hash:
                    raise CandidateValidationError(
                        "candidate evidence fragment hash does not match its excerpt"
                    )

    def _invoke_technical(
        self, stage: str, component: str, call: Callable[[], T]
    ) -> T:
        try:
            result = call()
            return result
        except TechnicalFailure as first:
            if first.component == "policy_guard":
                self.log.technical(
                    stage,
                    first.component,
                    first.summary,
                    "Policy violations are not retryable.",
                    "unresolved",
                )
                raise
            if self.technical_retries_used >= self.spec.max_technical_retries:
                self.log.technical(
                    stage,
                    first.component,
                    first.summary,
                    "No retry remained.",
                    "unresolved",
                )
                raise
            self.technical_retries_used += 1
            try:
                result = call()
            except TechnicalFailure as second:
                self.log.technical(
                    stage,
                    second.component,
                    second.summary,
                    "The single exact technical retry also failed.",
                    "unresolved",
                )
                raise
            self.log.technical(
                stage,
                first.component,
                first.summary,
                "The exact same call succeeded on the single retry.",
                "resolved",
            )
            return result

    def _plan_correction(self, gate: StopGateResult) -> CorrectionRequest:
        target = min(
            (gap.earliest_checkpoint for gap in gate.gaps),
            key=CHECKPOINT_RANK.__getitem__,
        )
        refs = tuple(
            dict.fromkeys(ref for gap in gate.gaps for ref in gap.affected_refs)
        )
        scopes = tuple(
            dict.fromkeys(scope for gap in gate.gaps for scope in gap.source_scope)
        )
        return CorrectionRequest(
            correction_round=self.semantic_corrections_used,
            target_checkpoint=target,
            target_refs=refs,
            source_scope=scopes,
            gaps=gate.gaps,
            immutable_run_identity=self.spec.immutable_run_identity,
        )

    def _finalize(
        self, status: str, gate: StopGateResult
    ) -> BuilderRunResult:
        gdu = copy.deepcopy(self.working.data)
        self._stamp_manifest(gdu, status)

        if status == "frozen":
            self.log.freeze(
                gdu["manifest"]["gdu_identity"]["artifact_version"], gate
            )
            try:
                paths = self.writer.publish(gdu, self.log.events, self.spec.output_dir)
            except TechnicalFailure as first:
                # The prospective freeze was never published, so remove it before
                # recording the technical event and constructing a new final freeze.
                self.log.discard_unpublished_freeze()
                paths = self._retry_publish(gdu, status, gate, first)
        else:
            try:
                paths = self.writer.publish(gdu, self.log.events, self.spec.output_dir)
            except TechnicalFailure as first:
                paths = self._retry_publish(gdu, status, gate, first)

        outcome = "frozen_complete" if status == "frozen" else "provisional_complete"
        self.state_trace.append(outcome)
        return self._result(
            outcome,
            paths,
            "cp6",
            "Stop gate passed." if status == "frozen" else "Correction limit reached.",
        )

    def _retry_publish(
        self,
        gdu: Mapping[str, Any],
        status: str,
        gate: StopGateResult,
        first: TechnicalFailure,
    ) -> tuple[Path, Path, Path]:
        if self.technical_retries_used >= self.spec.max_technical_retries:
            self.log.technical(
                "publish",
                first.component,
                first.summary,
                "No retry remained.",
                "unresolved",
            )
            raise first
        self.technical_retries_used += 1
        self.log.technical(
            "publish",
            first.component,
            first.summary,
            "Retrying the exact same staged package publication.",
            "workaround",
        )
        if status == "frozen":
            self.log.freeze(
                gdu["manifest"]["gdu_identity"]["artifact_version"], gate
            )
        try:
            return self.writer.publish(gdu, self.log.events, self.spec.output_dir)
        except TechnicalFailure as second:
            if status == "frozen" and self.log.events[-1]["event_type"] == "freeze":
                self.log.discard_unpublished_freeze()
            self.log.technical(
                "publish",
                second.component,
                second.summary,
                "The single exact technical retry also failed.",
                "unresolved",
            )
            raise second

    def _stamp_manifest(self, gdu: dict[str, Any], status: str) -> None:
        manifest = gdu["manifest"]
        manifest["gdu_identity"]["status"] = status
        manifest["gdu_identity"]["built_at"] = self.clock.now()
        manifest["source_identity"]["original_filename"] = self.spec.source_pdf.name
        manifest["source_identity"]["source_sha256"] = self._sha256(
            self.spec.source_pdf
        )
        manifest["source_identity"]["extracted_text_sha256"] = self._sha256(
            self.spec.extracted_text
        )
        if self.source_identity is not None:
            manifest["source_identity"]["pdf_page_count"] = (
                self.source_identity.pdf_page_count
            )
            manifest["source_identity"]["extraction_system"] = (
                self.source_identity.extraction_system
            )
        manifest["build_identity"] = {
            "protocol_name": self.spec.protocol_name,
            "protocol_version": self.spec.protocol_version,
            "protocol_sha256": self.spec.protocol_sha256,
            "model_id": self.spec.model_id,
            "reasoning_effort": self.spec.reasoning_effort,
            "config_or_prompt_sha256": self.spec.config_or_prompt_sha256,
            "build_log_ref": "build_log.jsonl",
        }

    def _preserve_complete_snapshot(self) -> tuple[Path, ...]:
        required = {
            "manifest",
            "physical_structure",
            "semantic_units",
            "assertions",
            "relations",
            "generative_plan",
            "evidence",
        }
        if not required.issubset(self.working.data):
            return ()
        gdu = copy.deepcopy(self.working.data)
        try:
            self._stamp_manifest(gdu, "provisional")
            return self.writer.publish(gdu, self.log.events, self.spec.output_dir)
        except (TechnicalFailure, KeyError):
            return ()

    def _verify_inputs(self) -> str | None:
        paths = (
            self.spec.source_pdf,
            self.spec.extracted_text,
            self.spec.gdu_schema,
            self.spec.build_log_schema,
            self.spec.protocol_path,
        )
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            return "missing input: " + ", ".join(missing)
        expected = (
            (self.spec.gdu_schema, self.spec.gdu_schema_sha256),
            (self.spec.build_log_schema, self.spec.build_log_schema_sha256),
            (self.spec.protocol_path, self.spec.protocol_sha256),
        )
        for path, digest in expected:
            if not SHA256.fullmatch(digest) or self._sha256(path) != digest:
                return f"hash mismatch: {path}"
        if (
            self.spec.expected_source_sha256 is not None
            and self._sha256(self.spec.source_pdf)
            != self.spec.expected_source_sha256
        ):
            return "source PDF hash mismatch"
        if (
            self.spec.expected_extracted_text_sha256 is not None
            and self._sha256(self.spec.extracted_text)
            != self.spec.expected_extracted_text_sha256
        ):
            return "extracted text hash mismatch"
        if not SHA256.fullmatch(self.spec.config_or_prompt_sha256):
            return "config_or_prompt_sha256 is invalid"
        if not self.spec.model_id or not self.spec.reasoning_effort:
            return "model identity fields must be non-empty"
        if self.spec.max_semantic_corrections != 2:
            return "max_semantic_corrections must equal 2"
        if self.spec.max_technical_retries != 1:
            return "max_technical_retries must equal 1"
        if not self.spec.single_builder:
            return "single_builder must be true"
        if self.spec.external_knowledge_allowed:
            return "external knowledge must be disabled"
        if self.spec.output_dir.exists():
            return "output directory must not already exist"
        output = self.spec.output_dir.resolve()
        if any(path.resolve().is_relative_to(output) for path in paths):
            return "output directory cannot contain protected input"
        if self.source_reader is None:
            return "SourceReader must be injected"
        if self.source_reader.pdf_path.resolve() != self.spec.source_pdf.resolve():
            return "SourceReader PDF does not match BuilderRunSpec"
        required_stages = {*CHECKPOINTS, "cp6"}
        if set(self.source_plan) != required_stages:
            return "checkpoint source plan must define exactly cp1 through cp6"
        try:
            identity = self.source_reader.inspect()
        except TechnicalFailure as exc:
            return f"SourceReader input rejected: {exc.summary}"
        if identity.source_sha256 != self._sha256(self.spec.source_pdf):
            return "SourceReader identity does not match Builder source"
        if (
            self.spec.expected_extraction_system is not None
            and identity.extraction_system
            != self.spec.expected_extraction_system
        ):
            return "SourceReader extraction system does not match BuilderRunSpec"
        for stage, request in self.source_plan.items():
            if not request.purpose.strip():
                return f"{stage} source request purpose must be non-empty"
            if request.modalities != ("text",):
                return f"{stage} source request must use text-only modality"
            if not request.page_ranges:
                return f"{stage} source request must include a page range"
            for start, end in request.page_ranges:
                if start < 1 or end < start or end > identity.pdf_page_count:
                    return (
                        f"{stage} source page range {start}-{end} is outside "
                        f"1-{identity.pdf_page_count}"
                    )
        self.source_identity = identity
        return None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _result(
        self,
        outcome: str,
        paths: tuple[Path, ...],
        checkpoint: str,
        summary: str,
    ) -> BuilderRunResult:
        return BuilderRunResult(
            outcome=outcome,  # type: ignore[arg-type]
            artifact_paths=paths,
            semantic_corrections_used=self.semantic_corrections_used,
            technical_retries_used=self.technical_retries_used,
            final_checkpoint=checkpoint,
            public_summary=summary,
            state_trace=tuple(self.state_trace),
        )
