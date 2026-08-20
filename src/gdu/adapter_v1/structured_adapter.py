from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, cast

from gdu.builder_v0.types import (
    AdapterStageResult,
    CandidateBundle,
    CandidateObject,
    CheckpointName,
    CorrectionRequest,
    Gap,
    ObjectMutation,
    RevisionRecord,
    SourcePacket,
    StopGateResult,
    TechnicalFailure,
)


class Transport(Protocol):
    """Provider-neutral structured response transport."""

    def invoke(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class TranscriptTransport:
    """Replay preregistered structured responses without network or model calls."""

    def __init__(self, responses: Sequence[Mapping[str, Any]]) -> None:
        self._responses = [copy.deepcopy(dict(response)) for response in responses]
        self.requests: list[dict[str, Any]] = []

    def invoke(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        self.requests.append(copy.deepcopy(dict(request)))
        if not self._responses:
            raise TechnicalFailure(
                "adapter_transport", "the preregistered transcript is exhausted"
            )
        return self._responses.pop(0)

    @property
    def remaining(self) -> int:
        return len(self._responses)


class StructuredUnderstandingAdapter:
    """Translate frozen Builder dataclasses to/from a validated JSON contract."""

    def __init__(
        self,
        transport: Transport,
        run_identity: tuple[str, str, str],
        request_schema: Path,
        response_schema: Path,
    ) -> None:
        self.transport = transport
        self.run_identity = run_identity
        self._request_validator = self._validator(request_schema)
        self._response_validator = self._validator(response_schema)

    def propose(
        self,
        stage: CheckpointName,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        request = self._request(
            "propose", stage, source_packet, public_working_view, None
        )
        return self._invoke_and_parse(request, "propose", stage)

    def revise(
        self,
        request: CorrectionRequest,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        payload = self._request(
            "revise",
            request.target_checkpoint,
            source_packet,
            public_working_view,
            request,
        )
        return self._invoke_and_parse(
            payload, "revise", request.target_checkpoint
        )

    def _invoke_and_parse(
        self, request: dict[str, Any], mode: str, stage: str
    ) -> AdapterStageResult:
        self._validate(self._request_validator, request, "request")
        try:
            raw = self.transport.invoke(copy.deepcopy(request))
        except TechnicalFailure:
            raise
        except Exception as exc:
            raise TechnicalFailure("adapter_transport", str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise TechnicalFailure(
                "adapter_contract", "transport response must be a JSON object"
            )
        response = copy.deepcopy(dict(raw))
        self._validate(self._response_validator, response, "response")
        if response["mode"] != mode or response["stage"] != stage:
            raise TechnicalFailure(
                "adapter_contract",
                f"expected {mode}/{stage}, received {response['mode']}/{response['stage']}",
            )
        try:
            return self._parse_response(response)
        except (KeyError, TypeError, ValueError) as exc:
            raise TechnicalFailure("adapter_contract", str(exc)) from exc

    def _request(
        self,
        mode: str,
        stage: str,
        packet: SourcePacket,
        public_view: Mapping[str, Any],
        correction: CorrectionRequest | None,
    ) -> dict[str, Any]:
        model_id, reasoning_effort, config_hash = self.run_identity
        value: dict[str, Any] = {
            "contract_version": "gdu-adapter-v1",
            "mode": mode,
            "stage": stage,
            "run_identity": {
                "model_id": model_id,
                "reasoning_effort": reasoning_effort,
                "config_or_prompt_sha256": config_hash,
            },
            "source_packet": {
                "source_document_id": packet.source_document_id,
                "request_identity": packet.request_identity,
                "pdf_fragments": [
                    {
                        "page": fragment.page,
                        "locator": fragment.locator,
                        "excerpt": fragment.excerpt,
                        "fragment_sha256": fragment.fragment_sha256,
                    }
                    for fragment in packet.pdf_fragments
                ],
                "navigation_text": list(packet.navigation_text),
                "retrieval_notes": list(packet.retrieval_notes),
            },
            "public_working_view": copy.deepcopy(dict(public_view)),
            "policy": {
                "external_knowledge_allowed": False,
                "paid_remote_calls_allowed": False,
            },
        }
        if correction is not None:
            value["correction_request"] = {
                "correction_round": correction.correction_round,
                "target_checkpoint": correction.target_checkpoint,
                "target_refs": list(correction.target_refs),
                "source_scope": [
                    {"start": start, "end": end}
                    for start, end in correction.source_scope
                ],
                "gaps": [self._gap_json(gap) for gap in correction.gaps],
                "immutable_run_identity": {
                    "model_id": correction.immutable_run_identity[0],
                    "reasoning_effort": correction.immutable_run_identity[1],
                    "config_or_prompt_sha256": correction.immutable_run_identity[2],
                },
            }
        return value

    def _parse_response(self, value: Mapping[str, Any]) -> AdapterStageResult:
        stage = cast(CheckpointName, value["stage"])
        identity = value["observed_run_identity"]
        observed = (
            identity["model_id"],
            identity["reasoning_effort"],
            identity["config_or_prompt_sha256"],
        )
        stop_gate = (
            self._stop_gate(value["stop_gate"])
            if "stop_gate" in value
            else None
        )
        bundle = None
        if stage != "cp6":
            bundle = CandidateBundle(
                stage=stage,
                objects=tuple(
                    CandidateObject(
                        kind=item["kind"],
                        handle=item["handle"],
                        fields=copy.deepcopy(item["fields"]),
                        source_authority=item["source_authority"],
                    )
                    for item in value["objects"]
                ),
                manifest=copy.deepcopy(value.get("manifest")),
                generative_plan=copy.deepcopy(value.get("generative_plan")),
                mutations=tuple(
                    ObjectMutation(
                        operation=item["operation"],
                        target_ref=item["target_ref"],
                        replacement_fields=copy.deepcopy(
                            item["replacement_fields"]
                        ),
                    )
                    for item in value["mutations"]
                ),
            )
        revisions = tuple(
            RevisionRecord(
                before_summary=item["before_summary"],
                after_summary=item["after_summary"],
                change_type=item["change_type"],
                trigger_evidence_refs=tuple(item["trigger_evidence_refs"]),
                affected_refs=tuple(item["affected_refs"]),
                surviving_alternative_refs=tuple(
                    item["surviving_alternative_refs"]
                ),
                rationale=item["rationale"],
            )
            for item in value["revisions"]
        )
        return AdapterStageResult(
            stage=stage,
            bundle=bundle,
            stop_gate=stop_gate,
            result_summary=value["result_summary"],
            revisions=revisions,
            observed_run_identity=observed,
        )

    @classmethod
    def _stop_gate(cls, value: Mapping[str, Any]) -> StopGateResult:
        return StopGateResult(
            coverage=value["coverage"],
            evidence=value["evidence"],
            stability=value["stability"],
            cross_carrier=value["cross_carrier"],
            cross_section=value["cross_section"],
            negative_boundary=value["negative_boundary"],
            gaps=tuple(cls._gap(item) for item in value["gaps"]),
            summary=value["summary"],
        )

    @staticmethod
    def _gap(value: Mapping[str, Any]) -> Gap:
        return Gap(
            gap_id=value["gap_id"],
            gate_dimension=value["gate_dimension"],
            check_kind=value["check_kind"],
            affected_refs=tuple(value["affected_refs"]),
            source_scope=tuple(
                (item["start"], item["end"]) for item in value["source_scope"]
            ),
            reason=value["reason"],
            earliest_checkpoint=value["earliest_checkpoint"],
            requested_action=value["requested_action"],
        )

    @staticmethod
    def _gap_json(gap: Gap) -> dict[str, Any]:
        return {
            "gap_id": gap.gap_id,
            "gate_dimension": gap.gate_dimension,
            "check_kind": gap.check_kind,
            "affected_refs": list(gap.affected_refs),
            "source_scope": [
                {"start": start, "end": end} for start, end in gap.source_scope
            ],
            "reason": gap.reason,
            "earliest_checkpoint": gap.earliest_checkpoint,
            "requested_action": gap.requested_action,
        }

    @staticmethod
    def _validator(path: Path) -> Any:
        try:
            import jsonschema
        except ModuleNotFoundError as exc:
            raise TechnicalFailure(
                "adapter_contract", "jsonschema is required"
            ) from exc
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TechnicalFailure("adapter_contract", str(exc)) from exc
        return jsonschema.Draft202012Validator(schema)

    @staticmethod
    def _validate(validator: Any, value: Mapping[str, Any], label: str) -> None:
        errors = sorted(
            validator.iter_errors(value), key=lambda error: list(error.path)
        )
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.absolute_path) or "$"
            raise TechnicalFailure(
                "adapter_contract",
                f"invalid {label} at {location}: {first.message}",
            )
