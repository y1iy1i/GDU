from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Mapping

from .types import (
    AdapterStageResult,
    CandidateBundle,
    CandidateObject,
    CheckpointName,
    CorrectionRequest,
    SourcePacket,
    StopGateResult,
    TechnicalFailure,
)


STAGE_KINDS: dict[str, tuple[str, ...]] = {
    "cp1": ("evidence", "physical_structure"),
    "cp2": ("semantic_unit", "assertion"),
    "cp3": ("interpretation_group",),
    "cp4": ("relation",),
}


class GduFixtureAdapter:
    """Replay a complete GDU fixture through the public Builder checkpoints."""

    def __init__(
        self,
        fixture: Mapping[str, Any],
        run_identity: tuple[str, str, str],
        strict_source_fragments: bool = True,
    ) -> None:
        self.fixture = copy.deepcopy(dict(fixture))
        self.run_identity = run_identity
        self.strict_source_fragments = strict_source_fragments
        self._objects = self._index_objects()

    def propose(
        self,
        stage: CheckpointName,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        del public_working_view
        if stage == "cp6":
            return AdapterStageResult(
                stage="cp6",
                stop_gate=StopGateResult(
                    coverage="passed",
                    evidence="passed",
                    stability="passed",
                    cross_carrier="passed",
                    cross_section="passed",
                    negative_boundary="passed",
                    summary="Frozen fixture replay passed all registered stop gates.",
                ),
                result_summary="All six deterministic fixture checks passed.",
                observed_run_identity=self.run_identity,
            )

        objects: tuple[CandidateObject, ...] = ()
        if stage in STAGE_KINDS:
            objects = self._candidate_objects(stage, source_packet)
        bundle = CandidateBundle(
            stage=stage,
            objects=objects,
            manifest=(copy.deepcopy(self.fixture["manifest"]) if stage == "cp1" else None),
            generative_plan=(
                copy.deepcopy(self.fixture["generative_plan"])
                if stage == "cp5"
                else None
            ),
        )
        return AdapterStageResult(
            stage=stage,
            bundle=bundle,
            result_summary=f"Replayed registered fixture content for {stage}.",
            observed_run_identity=self.run_identity,
        )

    def revise(
        self,
        request: CorrectionRequest,
        source_packet: SourcePacket,
        public_working_view: Mapping[str, Any],
    ) -> AdapterStageResult:
        del request, source_packet, public_working_view
        raise TechnicalFailure(
            "fixture_adapter",
            "the deterministic fixture adapter has no semantic correction script",
        )

    def _candidate_objects(
        self, stage: str, source_packet: SourcePacket
    ) -> tuple[CandidateObject, ...]:
        records = [
            (kind, record)
            for kind in STAGE_KINDS[stage]
            for record in self._objects[kind]
        ]
        local = {
            record["id"]: f"{kind}_{index}"
            for index, (kind, record) in enumerate(records, start=1)
        }
        candidates: list[CandidateObject] = []
        for kind, record in records:
            original_id = record["id"]
            fields = copy.deepcopy(record)
            del fields["id"]
            fields = self._replace_local_refs(fields, local)
            if kind == "evidence" and self.strict_source_fragments:
                self._ground_evidence(fields, source_packet)
            candidates.append(
                CandidateObject(
                    kind=kind, handle=local[original_id], fields=fields
                )
            )
        return tuple(candidates)

    def _index_objects(self) -> dict[str, list[dict[str, Any]]]:
        assertions = self.fixture["assertions"]
        return {
            "physical_structure": self.fixture["physical_structure"],
            "semantic_unit": self.fixture["semantic_units"],
            "assertion": assertions["items"],
            "interpretation_group": assertions["interpretation_groups"],
            "relation": self.fixture["relations"],
            "evidence": self.fixture["evidence"],
        }

    @classmethod
    def _replace_local_refs(cls, value: Any, local: Mapping[str, str]) -> Any:
        if isinstance(value, str):
            return f"@{local[value]}" if value in local else value
        if isinstance(value, list):
            return [cls._replace_local_refs(item, local) for item in value]
        if isinstance(value, dict):
            return {
                key: cls._replace_local_refs(item, local)
                for key, item in value.items()
            }
        return value

    @classmethod
    def _ground_evidence(
        cls, fields: dict[str, Any], source_packet: SourcePacket
    ) -> None:
        pages = {fragment.page: fragment for fragment in source_packet.pdf_fragments}
        for fragment in fields.get("fragments", []):
            page = fragment.get("page")
            authoritative = pages.get(page)
            if authoritative is None:
                raise TechnicalFailure(
                    "fixture_adapter",
                    f"fixture evidence page {page} is absent from the authorized source packet",
                )
            excerpt = cls._normalize(str(fragment.get("excerpt", "")))
            if not excerpt or excerpt not in authoritative.excerpt:
                fragment["excerpt"] = authoritative.excerpt
                fragment["locator"] = (
                    f"{fragment.get('locator', 'fixture locator')} "
                    f"[strict text-layer fallback: {authoritative.locator}]"
                )
            fragment["fragment_sha256"] = hashlib.sha256(
                str(fragment["excerpt"]).encode("utf-8")
            ).hexdigest()

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
