from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from gdu.adapter_v1 import StructuredUnderstandingAdapter, TranscriptTransport
from gdu.builder_v0.fixture_adapter import GduFixtureAdapter
from gdu.builder_v0.orchestrator import BuilderOrchestrator
from gdu.builder_v0.source_reader import SourceReader
from gdu.builder_v0.testing import DeterministicClock
from gdu.builder_v0.types import (
    AdapterStageResult,
    BuilderRunSpec,
    PdfPageFragment,
    SourcePacket,
    SourceRequest,
    TechnicalFailure,
)


ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA = ROOT / "adapter-request-v1.schema.json"
RESPONSE_SCHEMA = ROOT / "adapter-response-v1.schema.json"
IDENTITY = ("transcript-model-v1", "not_applicable", "a" * 64)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fragment(page: int, text: str) -> PdfPageFragment:
    return PdfPageFragment(
        page=page,
        locator=f"physical-page:{page}",
        excerpt=text,
        fragment_sha256=sha256_bytes(text.encode("utf-8")),
    )


def packet() -> SourcePacket:
    return SourcePacket(
        source_document_id="litong-2025-annual-report",
        request_identity="b" * 64,
        pdf_fragments=(fragment(1, "authorized source text"),),
    )


def identity_json() -> dict[str, str]:
    return {
        "model_id": IDENTITY[0],
        "reasoning_effort": IDENTITY[1],
        "config_or_prompt_sha256": IDENTITY[2],
    }


def passed_cp6(stage: str = "cp6") -> dict[str, Any]:
    return {
        "contract_version": "gdu-adapter-v1",
        "mode": "propose",
        "stage": stage,
        "result_summary": "All registered gates passed.",
        "objects": [],
        "mutations": [],
        "revisions": [],
        "stop_gate": {
            "coverage": "passed",
            "evidence": "passed",
            "stability": "passed",
            "cross_carrier": "passed",
            "cross_section": "passed",
            "negative_boundary": "passed",
            "gaps": [],
            "summary": "All registered gates passed.",
        },
        "observed_run_identity": identity_json(),
    }


def adapter(responses: list[Mapping[str, Any]]) -> StructuredUnderstandingAdapter:
    return StructuredUnderstandingAdapter(
        TranscriptTransport(responses), IDENTITY, REQUEST_SCHEMA, RESPONSE_SCHEMA
    )


class AdapterV1ContractTests(unittest.TestCase):
    def test_request_contains_no_pdf_path_or_paid_permission(self) -> None:
        transport = TranscriptTransport([passed_cp6()])
        active = StructuredUnderstandingAdapter(
            transport, IDENTITY, REQUEST_SCHEMA, RESPONSE_SCHEMA
        )

        result = active.propose("cp6", packet(), {})

        self.assertTrue(result.stop_gate.passed)
        request = transport.requests[0]
        self.assertNotIn("path", json.dumps(request))
        self.assertFalse(request["policy"]["paid_remote_calls_allowed"])
        self.assertFalse(request["policy"]["external_knowledge_allowed"])

    def test_response_stage_must_match_request(self) -> None:
        response = passed_cp6(stage="cp4")
        del response["stop_gate"]
        active = adapter([response])
        with self.assertRaisesRegex(TechnicalFailure, "expected propose/cp6"):
            active.propose("cp6", packet(), {})

    def test_cp6_cannot_return_objects(self) -> None:
        response = passed_cp6()
        response["objects"] = [
            {
                "kind": "assertion",
                "handle": "hidden",
                "fields": {},
                "source_authority": "pdf",
            }
        ]
        with self.assertRaisesRegex(TechnicalFailure, "invalid response"):
            adapter([response]).propose("cp6", packet(), {})

    def test_failed_gate_without_gap_is_a_contract_failure(self) -> None:
        response = passed_cp6()
        response["stop_gate"]["evidence"] = "failed"
        with self.assertRaisesRegex(TechnicalFailure, "failed stop gate"):
            adapter([response]).propose("cp6", packet(), {})

    def test_transcript_exhaustion_is_a_technical_failure(self) -> None:
        active = adapter([])
        with self.assertRaisesRegex(TechnicalFailure, "transcript is exhausted"):
            active.propose("cp6", packet(), {})


class FixtureBackend:
    def __init__(self) -> None:
        self.pages = [f"Physical page {page}." for page in range(1, 238)]
        self.pages[0] = "江苏利通电子股份有限公司2025年年度报告"
        self.pages[7] = "第二节 公司简介和主要财务指标"
        self.pages[8] = (
            "归属于上市公司股东的净利润 292,589,095.99；"
            "归属于上市公司股东的扣除非经常性损益后的净利润 235,942,443.22。"
        )
        self.pages[10] = "非经常性损益合计 56,646,652.77 元。"

    @property
    def name(self) -> str:
        return "adapter-v1-fixture-backend"

    def page_count(self, path: Path) -> int:
        return len(self.pages)

    def extract_page_text(self, path: Path, page_number: int) -> str:
        return self.pages[page_number - 1]


def response_json(result: AdapterStageResult) -> dict[str, Any]:
    value: dict[str, Any] = {
        "contract_version": "gdu-adapter-v1",
        "mode": "propose",
        "stage": result.stage,
        "result_summary": result.result_summary,
        "objects": [],
        "mutations": [],
        "revisions": [],
        "observed_run_identity": identity_json(),
    }
    if result.bundle is not None:
        value["objects"] = [
            {
                "kind": item.kind,
                "handle": item.handle,
                "fields": copy.deepcopy(dict(item.fields)),
                "source_authority": item.source_authority,
            }
            for item in result.bundle.objects
        ]
        if result.bundle.manifest is not None:
            value["manifest"] = copy.deepcopy(dict(result.bundle.manifest))
        if result.bundle.generative_plan is not None:
            value["generative_plan"] = copy.deepcopy(
                dict(result.bundle.generative_plan)
            )
    if result.stop_gate is not None:
        gate = result.stop_gate
        value["stop_gate"] = {
            "coverage": gate.coverage,
            "evidence": gate.evidence,
            "stability": gate.stability,
            "cross_carrier": gate.cross_carrier,
            "cross_section": gate.cross_section,
            "negative_boundary": gate.negative_boundary,
            "gaps": [],
            "summary": gate.summary,
        }
    return value


class AdapterV1BuilderIntegrationTests(unittest.TestCase):
    def test_transcript_adapter_completes_frozen_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            pdf = work / "paper.pdf"
            text = work / "paper.txt"
            pdf.write_bytes(b"%PDF-1.4\nadapter-v1-fixture\n%%EOF\n")
            text.write_text("navigation", encoding="utf-8")
            backend = FixtureBackend()
            fixture = json.loads((ROOT / "gdu.example.json").read_text(encoding="utf-8"))
            fixed_packet = SourcePacket(
                source_document_id="litong-2025-annual-report",
                request_identity="c" * 64,
                pdf_fragments=tuple(
                    fragment(page, backend.pages[page - 1])
                    for page in (1, 8, 9, 11)
                ),
            )
            fixture_adapter = GduFixtureAdapter(fixture, IDENTITY)
            responses = [
                response_json(fixture_adapter.propose(stage, fixed_packet, {}))
                for stage in ("cp1", "cp2", "cp3", "cp4", "cp5", "cp6")
            ]
            transport = TranscriptTransport(responses)
            structured = StructuredUnderstandingAdapter(
                transport, IDENTITY, REQUEST_SCHEMA, RESPONSE_SCHEMA
            )
            source_plan = {
                stage: SourceRequest(
                    purpose=f"adapter v1 integration {stage}",
                    page_ranges=((1, 1), (8, 9), (11, 11)),
                )
                for stage in ("cp1", "cp2", "cp3", "cp4", "cp5", "cp6")
            }
            spec = BuilderRunSpec(
                run_id="adapter-v1-integration",
                source_pdf=pdf,
                extracted_text=text,
                gdu_schema=ROOT / "gdu.schema.json",
                gdu_schema_sha256=sha256_file(ROOT / "gdu.schema.json"),
                build_log_schema=ROOT / "build_log.schema.json",
                build_log_schema_sha256=sha256_file(ROOT / "build_log.schema.json"),
                protocol_path=ROOT / "BUILDER_PROTOCOL_V2.md",
                protocol_name="gdu-builder-protocol",
                protocol_version="v2",
                protocol_sha256=sha256_file(ROOT / "BUILDER_PROTOCOL_V2.md"),
                config_or_prompt_sha256=IDENTITY[2],
                model_id=IDENTITY[0],
                reasoning_effort=IDENTITY[1],
                output_dir=work / "output",
                checkpoint_source_requests=source_plan,
            )
            result = BuilderOrchestrator(
                spec,
                structured,
                DeterministicClock(),
                source_reader=SourceReader(
                    pdf, "litong-2025-annual-report", backend
                ),
            ).build()

            self.assertEqual("frozen_complete", result.outcome)
            self.assertEqual(6, len(transport.requests))
            self.assertEqual(0, transport.remaining)
            self.assertTrue(all("path" not in json.dumps(item) for item in transport.requests))


if __name__ == "__main__":
    unittest.main()
