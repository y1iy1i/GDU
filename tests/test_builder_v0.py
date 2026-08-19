from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.artifact_writer import ArtifactWriterValidator  # noqa: E402
from gdu.builder_v0.id_allocator import CanonicalIdAllocator  # noqa: E402
from gdu.builder_v0.log_writer import BuildLogWriter  # noqa: E402
from gdu.builder_v0.orchestrator import BuilderOrchestrator  # noqa: E402
from gdu.builder_v0.source_reader import SourceReader  # noqa: E402
from gdu.builder_v0.testing import (  # noqa: E402
    DeterministicClock,
    FixedUnderstandingAdapter,
)
from gdu.builder_v0.types import (  # noqa: E402
    AdapterStageResult,
    BuilderRunSpec,
    CandidateBundle,
    CandidateObject,
    CandidateValidationError,
    Gap,
    ObjectMutation,
    RevisionRecord,
    StopGateResult,
    SourceRequest,
    TechnicalFailure,
)
from gdu.validator_v0 import validate_file, validate_schema  # noqa: E402


try:
    import pypdf  # noqa: F401

    REAL_PYPDF_AVAILABLE = True
except ModuleNotFoundError:
    REAL_PYPDF_AVAILABLE = False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_refs(value: Any, local_ids: dict[str, str]) -> Any:
    if isinstance(value, str) and value in local_ids:
        return "@" + local_ids[value]
    if isinstance(value, list):
        return [rewrite_refs(item, local_ids) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_refs(item, local_ids) for key, item in value.items()}
    return value


def candidate(
    kind: str, value: dict[str, Any], handle: str, local_ids: dict[str, str]
) -> CandidateObject:
    fields = copy.deepcopy(value)
    fields.pop("id")
    fields = rewrite_refs(fields, local_ids)
    return CandidateObject(kind=kind, handle=handle, fields=fields)  # type: ignore[arg-type]


class AlwaysFailWriter(ArtifactWriterValidator):
    def __init__(self, gdu_schema: Path, build_log_schema: Path, point: str) -> None:
        super().__init__(gdu_schema, build_log_schema)
        self.point = point
        self.calls = 0

    def publish(self, gdu, events, output_dir):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise TechnicalFailure("artifact_writer", f"injected failure at {self.point}")


class BuilderFixturePdfBackend:
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
        return "builder-fixture-pdf-backend-v0"

    def page_count(self, path: Path) -> int:
        return len(self.pages)

    def extract_page_text(self, path: Path, page_number: int) -> str:
        return self.pages[page_number - 1]


class FlakyBuilderPdfBackend(BuilderFixturePdfBackend):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures_remaining = failures
        self.extract_calls = 0

    def extract_page_text(self, path: Path, page_number: int) -> str:
        self.extract_calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise TechnicalFailure("source_reader", "injected source read failure")
        return super().extract_page_text(path, page_number)


class BuilderV0P0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.pdf = self.work / "paper.pdf"
        self.text = self.work / "paper.txt"
        self.pdf.write_bytes(b"%PDF-1.4\nfixed builder fixture\n%%EOF\n")
        self.text.write_text("fixed navigation text", encoding="utf-8")
        self.example = json.loads((ROOT / "gdu.example.json").read_text())
        self.spec = BuilderRunSpec(
            run_id="builder-test-run",
            source_pdf=self.pdf,
            extracted_text=self.text,
            gdu_schema=ROOT / "gdu.schema.json",
            gdu_schema_sha256=sha256(ROOT / "gdu.schema.json"),
            build_log_schema=ROOT / "build_log.schema.json",
            build_log_schema_sha256=sha256(ROOT / "build_log.schema.json"),
            protocol_path=ROOT / "BUILDER_PROTOCOL_V2.md",
            protocol_name="gdu-builder-protocol",
            protocol_version="v2",
            protocol_sha256=sha256(ROOT / "BUILDER_PROTOCOL_V2.md"),
            config_or_prompt_sha256=sha256(ROOT / "BUILDER_PROTOCOL_V2.md"),
            model_id="fixed-adapter-v0",
            reasoning_effort="not_applicable",
            output_dir=self.work / "output",
            checkpoint_source_requests={
                stage: SourceRequest(
                    purpose=f"fixed source plan for {stage}",
                    page_ranges=((1, 1), (8, 9), (11, 11)),
                )
                for stage in ("cp1", "cp2", "cp3", "cp4", "cp5", "cp6")
            },
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def valid_bundles(self) -> dict[str, CandidateBundle]:
        cp1_ids = {
            **{item["id"]: f"e{i}" for i, item in enumerate(self.example["evidence"], 1)},
            **{
                item["id"]: f"ps{i}"
                for i, item in enumerate(self.example["physical_structure"], 1)
            },
        }
        cp1_objects = [
            candidate("evidence", item, cp1_ids[item["id"]], cp1_ids)
            for item in self.example["evidence"]
        ] + [
            candidate("physical_structure", item, cp1_ids[item["id"]], cp1_ids)
            for item in self.example["physical_structure"]
        ]

        cp2_ids = {
            **{
                item["id"]: f"a{i}"
                for i, item in enumerate(self.example["assertions"]["items"], 1)
            },
            **{
                item["id"]: f"u{i}"
                for i, item in enumerate(self.example["semantic_units"], 1)
            },
        }
        cp2_objects = [
            candidate("assertion", item, cp2_ids[item["id"]], cp2_ids)
            for item in self.example["assertions"]["items"]
        ] + [
            candidate("semantic_unit", item, cp2_ids[item["id"]], cp2_ids)
            for item in self.example["semantic_units"]
        ]

        cp4_objects = [
            candidate("relation", item, f"r{i}", {})
            for i, item in enumerate(self.example["relations"], 1)
        ]
        return {
            "cp1": CandidateBundle(
                stage="cp1",
                objects=tuple(cp1_objects),
                manifest=copy.deepcopy(self.example["manifest"]),
            ),
            "cp2": CandidateBundle(stage="cp2", objects=tuple(cp2_objects)),
            "cp3": CandidateBundle(stage="cp3"),
            "cp4": CandidateBundle(stage="cp4", objects=tuple(cp4_objects)),
            "cp5": CandidateBundle(
                stage="cp5",
                generative_plan=copy.deepcopy(self.example["generative_plan"]),
            ),
        }

    def passed_gate(self) -> StopGateResult:
        return StopGateResult(
            coverage="passed",
            evidence="passed",
            stability="passed",
            cross_carrier="passed",
            cross_section="passed",
            negative_boundary="passed",
            summary="All joint stop conditions passed.",
        )

    def failed_gate(self, suffix: str = "1") -> StopGateResult:
        gap = Gap(
            gap_id=f"gap-{suffix}",
            gate_dimension="evidence",
            check_kind="ordinary",
            affected_refs=("A-001",),
            source_scope=((8, 9),),
            reason="A supporting passage still needs verification.",
            earliest_checkpoint="cp3",
            requested_action="Recheck the specified assertion and pages.",
        )
        return StopGateResult(
            coverage="passed",
            evidence="failed",
            stability="passed",
            cross_carrier="passed",
            cross_section="passed",
            negative_boundary="passed",
            gaps=(gap,),
            summary="Evidence gate failed.",
        )

    def revision_result(self, number: int) -> AdapterStageResult:
        revision = RevisionRecord(
            before_summary=f"Before correction {number}.",
            after_summary=f"After correction {number}.",
            change_type="replace",
            trigger_evidence_refs=("E-002",),
            affected_refs=("A-001",),
            rationale="The specified PDF evidence changed the public interpretation.",
        )
        return AdapterStageResult(
            stage="cp3",
            bundle=CandidateBundle(stage="cp3"),
            result_summary=f"Targeted correction {number} completed.",
            revisions=(revision,),
        )

    def adapter(
        self,
        gates: list[Any] | None = None,
        revisions: list[Any] | None = None,
        overrides: dict[str, list[Any]] | None = None,
    ) -> FixedUnderstandingAdapter:
        bundles = self.valid_bundles()
        proposals: dict[str, list[Any]] = {
            stage: [
                AdapterStageResult(
                    stage=stage, bundle=bundle, result_summary=f"{stage} completed."
                )
            ]
            for stage, bundle in bundles.items()
        }
        proposals["cp6"] = [
            AdapterStageResult(stage="cp6", stop_gate=gate, result_summary="cp6")
            if isinstance(gate, StopGateResult)
            else gate
            for gate in (gates or [self.passed_gate()])
        ]
        if overrides:
            proposals.update(overrides)
        return FixedUnderstandingAdapter(proposals, revisions or [])

    def run_builder(
        self,
        adapter: FixedUnderstandingAdapter,
        spec: BuilderRunSpec | None = None,
        writer: ArtifactWriterValidator | None = None,
        backend: BuilderFixturePdfBackend | None = None,
        source_reader: SourceReader | None = None,
        navigation_text: dict[int, str] | None = None,
    ):
        active_spec = spec or self.spec
        builder = BuilderOrchestrator(
            active_spec,
            adapter,
            DeterministicClock(),
            source_reader=source_reader
            or SourceReader(
                active_spec.source_pdf,
                "builder-fixture-document",
                backend or BuilderFixturePdfBackend(),
            ),
            navigation_text=navigation_text,
            artifact_writer=writer,
        )
        return builder, builder.build()

    def load_log(self, result) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
        return [
            json.loads(line)
            for line in result.artifact_paths[1].read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_p0_01_main_flow_freezes_once(self) -> None:
        builder, result = self.run_builder(self.adapter())

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.semantic_corrections_used, 0)
        self.assertEqual(result.technical_retries_used, 0)
        self.assertEqual(len(result.artifact_paths), 3)
        self.assertEqual(
            [call[1] for call in builder.adapter.call_trace],
            ["cp1", "cp2", "cp3", "cp4", "cp5", "cp6"],
        )
        events = self.load_log(result)
        self.assertEqual([event["event_type"] for event in events].count("freeze"), 1)
        self.assertEqual(events[-1]["event_type"], "freeze")

    def test_p0_02_one_targeted_correction_then_pass(self) -> None:
        adapter = self.adapter(
            [self.failed_gate(), self.passed_gate()], [self.revision_result(1)]
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.semantic_corrections_used, 1)
        revision_call = [call for call in adapter.call_trace if call[0] == "revise"][0]
        request = revision_call[2]
        self.assertEqual(request.target_checkpoint, "cp3")
        self.assertEqual(request.target_refs, ("A-001",))
        self.assertEqual(request.source_scope, ((8, 9),))
        self.assertEqual(request.immutable_run_identity, self.spec.immutable_run_identity)
        self.assertEqual([c[1] for c in adapter.call_trace].count("cp1"), 1)

    def test_p0_03_two_corrections_then_pass(self) -> None:
        adapter = self.adapter(
            [self.failed_gate("1"), self.failed_gate("2"), self.passed_gate()],
            [self.revision_result(1), self.revision_result(2)],
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.semantic_corrections_used, 2)
        self.assertEqual(len([c for c in adapter.call_trace if c[0] == "revise"]), 2)

    def test_p0_04_two_failed_corrections_publish_provisional(self) -> None:
        adapter = self.adapter(
            [self.failed_gate("1"), self.failed_gate("2"), self.failed_gate("3")],
            [self.revision_result(1), self.revision_result(2)],
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "provisional_complete")
        self.assertEqual(result.semantic_corrections_used, 2)
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(gdu["manifest"]["gdu_identity"]["status"], "provisional")
        self.assertNotIn("freeze", [event["event_type"] for event in self.load_log(result)])
        self.assertTrue(result.artifact_paths[2].is_file())

    def test_p0_05_one_technical_failure_recovers(self) -> None:
        valid_cp2 = AdapterStageResult(
            stage="cp2", bundle=self.valid_bundles()["cp2"], result_summary="cp2"
        )
        adapter = self.adapter(
            overrides={
                "cp2": [
                    TechnicalFailure("fixed_adapter", "temporary interruption"),
                    valid_cp2,
                ]
            }
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.technical_retries_used, 1)
        technical = [e for e in self.load_log(result) if e["event_type"] == "technical"]
        self.assertEqual(technical[0]["outcome"], "resolved")

    def test_p0_06_second_technical_failure_ends_run(self) -> None:
        adapter = self.adapter(
            overrides={
                "cp2": [
                    TechnicalFailure("fixed_adapter", "first failure"),
                    TechnicalFailure("fixed_adapter", "retry failure"),
                ]
            }
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.technical_retries_used, 1)
        self.assertFalse(self.spec.output_dir.exists())

    def test_p0_07_technical_retry_is_global(self) -> None:
        valid_cp2 = AdapterStageResult(
            stage="cp2", bundle=self.valid_bundles()["cp2"], result_summary="cp2"
        )
        adapter = self.adapter(
            overrides={
                "cp2": [TechnicalFailure("fixed_adapter", "cp2"), valid_cp2],
                "cp5": [TechnicalFailure("fixed_adapter", "cp5")],
            }
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.technical_retries_used, 1)
        self.assertEqual([c[1] for c in adapter.call_trace].count("cp5"), 1)

    def test_p0_08_semantic_failure_does_not_use_technical_retry(self) -> None:
        adapter = self.adapter(
            [self.failed_gate("1"), self.failed_gate("2"), self.failed_gate("3")],
            [self.revision_result(1), self.revision_result(2)],
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "provisional_complete")
        self.assertEqual(result.technical_retries_used, 0)
        self.assertEqual(result.semantic_corrections_used, 2)

    def test_p0_09_malformed_response_uses_technical_retry(self) -> None:
        valid_cp2 = AdapterStageResult(
            stage="cp2", bundle=self.valid_bundles()["cp2"], result_summary="cp2"
        )
        adapter = self.adapter(overrides={"cp2": [object(), valid_cp2]})
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.technical_retries_used, 1)

    def test_p0_10_illegal_inputs_are_rejected_before_adapter(self) -> None:
        variants = [
            replace(self.spec, source_pdf=self.work / "missing.pdf"),
            replace(self.spec, gdu_schema_sha256="0" * 64),
            replace(self.spec, build_log_schema_sha256="0" * 64),
            replace(self.spec, max_semantic_corrections=3),
            replace(self.spec, external_knowledge_allowed=True),
            replace(self.spec, single_builder=False),
            replace(self.spec, output_dir=self.work),
        ]
        for index, spec in enumerate(variants):
            with self.subTest(index=index):
                adapter = self.adapter()
                _, result = self.run_builder(adapter, spec)
                self.assertEqual(result.outcome, "input_rejected")
                self.assertEqual(adapter.call_trace, [])

    def test_p0_11_orchestrator_allocates_ids_with_local_scope(self) -> None:
        allocator = CanonicalIdAllocator()
        first = allocator.canonicalize(
            CandidateBundle(
                stage="cp1",
                objects=(
                    CandidateObject(
                        kind="evidence",
                        handle="same",
                        fields={"modality": "text", "fragments": []},
                    ),
                ),
            )
        )
        second = allocator.canonicalize(
            CandidateBundle(
                stage="cp2",
                objects=(
                    CandidateObject(
                        kind="assertion",
                        handle="same",
                        fields={
                            "kind": "content",
                            "statement": "x",
                            "epistemic_origin": "source_attributed",
                            "assessment_complete": False,
                            "evidence_refs": ["E-001"],
                            "rationale": "x",
                        },
                    ),
                ),
            )
        )
        self.assertEqual(first[0][1]["id"], "E-001")
        self.assertEqual(second[0][1]["id"], "A-001")

    def test_p0_12_dangling_local_handle_is_rejected(self) -> None:
        allocator = CanonicalIdAllocator()
        invalid = CandidateBundle(
            stage="cp4",
            objects=(
                CandidateObject(
                    kind="relation",
                    handle="r",
                    fields={"from_ref": "@missing", "to_ref": "A-001"},
                ),
            ),
        )
        with self.assertRaises(CandidateValidationError):
            allocator.canonicalize(invalid)

        valid = CandidateBundle(
            stage="cp4",
            objects=(
                CandidateObject(
                    kind="relation",
                    handle="r",
                    fields={"from_ref": "A-001", "to_ref": "A-002"},
                ),
            ),
        )
        canonical = allocator.canonicalize(valid)
        self.assertEqual(canonical[0][1]["id"], "R-001")

    def test_p0_13_cp2_function_requires_closed_basis(self) -> None:
        schema = json.loads((ROOT / "gdu.schema.json").read_text())
        valid = copy.deepcopy(self.example)
        self.assertEqual(validate_schema(valid, schema), [])
        function = valid["assertions"]["items"][-1]
        function.pop("basis_assertion_refs")
        self.assertTrue(validate_schema(valid, schema))

    def test_p0_14_cp6_cannot_mutate_prior_objects_directly(self) -> None:
        illicit = CandidateBundle(
            stage="cp6",
            objects=(
                CandidateObject(
                    kind="assertion",
                    handle="hidden-change",
                    fields={"statement": "CP6 must not promote this."},
                ),
            ),
        )
        first = AdapterStageResult(
            stage="cp6", bundle=illicit, stop_gate=self.failed_gate()
        )
        adapter = self.adapter(
            [first, self.passed_gate()], [self.revision_result(1)]
        )
        _, result = self.run_builder(adapter)

        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(len(gdu["assertions"]["items"]), 6)
        self.assertIn("correction_1_cp3", result.state_trace)

    def test_p0_15_frozen_log_has_one_final_freeze_and_order(self) -> None:
        _, result = self.run_builder(self.adapter())
        events = self.load_log(result)
        self.assertEqual(
            [event["logical_time"] for event in events],
            list(range(1, len(events) + 1)),
        )
        self.assertEqual(len({event["event_id"] for event in events}), len(events))
        self.assertEqual(
            [i for i, event in enumerate(events) if event["event_type"] == "freeze"],
            [len(events) - 1],
        )
        self.assertEqual(
            events[-1]["stop_gate"],
            {"coverage": "passed", "evidence": "passed", "stability": "passed"},
        )

    def test_p0_16_provisional_log_has_no_freeze(self) -> None:
        adapter = self.adapter(
            [self.failed_gate("1"), self.failed_gate("2"), self.failed_gate("3")],
            [self.revision_result(1), self.revision_result(2)],
        )
        _, result = self.run_builder(adapter)
        events = self.load_log(result)

        self.assertNotIn("freeze", [event["event_type"] for event in events])
        self.assertEqual(events[-1]["checkpoint_name"], "cp6")
        self.assertEqual(events[-1]["outcome"], "failed")

    def test_p0_17_artifact_hash_detects_later_change(self) -> None:
        _, result = self.run_builder(self.adapter())
        result.artifact_paths[0].write_text(
            result.artifact_paths[0].read_text() + " ", encoding="utf-8"
        )
        issues, setup_error = validate_file(
            result.artifact_paths[0],
            ROOT / "gdu.schema.json",
            result.artifact_paths[1],
            result.artifact_paths[2],
        )
        self.assertFalse(setup_error)
        self.assertIn("artifact_hash_mismatch", {issue.code for issue in issues})

    def test_p0_18_failed_publication_never_exposes_partial_package(self) -> None:
        for point in ("gdu", "log", "hash", "validation"):
            with self.subTest(point=point):
                spec = replace(self.spec, output_dir=self.work / f"output-{point}")
                writer = AlwaysFailWriter(
                    spec.gdu_schema, spec.build_log_schema, point
                )
                _, result = self.run_builder(self.adapter(), spec, writer)
                self.assertEqual(result.outcome, "technical_failed")
                self.assertEqual(writer.calls, 2)
                self.assertFalse(spec.output_dir.exists())

    def test_p1_01_multiple_gaps_return_to_earliest_checkpoint(self) -> None:
        early = replace(
            self.failed_gate("early").gaps[0],
            gap_id="gap-early",
            earliest_checkpoint="cp2",
        )
        late = replace(
            self.failed_gate("late").gaps[0],
            gap_id="gap-late",
            earliest_checkpoint="cp4",
        )
        gate = StopGateResult(
            coverage="failed",
            evidence="failed",
            stability="passed",
            cross_carrier="passed",
            cross_section="passed",
            negative_boundary="passed",
            gaps=(late, early),
            summary="Two bounded gaps.",
        )
        revision = AdapterStageResult(
            stage="cp2",
            bundle=CandidateBundle(stage="cp2"),
            result_summary="Earliest affected checkpoint revisited.",
        )
        adapter = self.adapter([gate, self.passed_gate()], [revision])
        _, result = self.run_builder(adapter)

        request = [c[2] for c in adapter.call_trace if c[0] == "revise"][0]
        self.assertEqual(request.target_checkpoint, "cp2")
        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual([c[1] for c in adapter.call_trace].count("cp1"), 1)

    def test_p1_02_correction_scope_blocks_unrelated_target(self) -> None:
        mutation = ObjectMutation(
            operation="replace",
            target_ref="A-002",
            replacement_fields={"statement": "Out-of-scope change."},
        )
        revision = RevisionRecord(
            before_summary="A-002 before.",
            after_summary="A-002 after.",
            change_type="replace",
            trigger_evidence_refs=("E-002",),
            affected_refs=("A-002",),
        )
        response = AdapterStageResult(
            stage="cp3",
            bundle=CandidateBundle(stage="cp3", mutations=(mutation,)),
            revisions=(revision,),
        )
        adapter = self.adapter([self.failed_gate()], [response])
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.technical_retries_used, 0)
        self.assertEqual(len(result.artifact_paths), 3)
        gdu = json.loads(result.artifact_paths[0].read_text())
        a2 = next(item for item in gdu["assertions"]["items"] if item["id"] == "A-002")
        self.assertNotEqual(a2["statement"], "Out-of-scope change.")

    def test_p1_03_adapter_cannot_change_run_identity(self) -> None:
        changed = AdapterStageResult(
            stage="cp2",
            bundle=self.valid_bundles()["cp2"],
            observed_run_identity=("different-model", "high", "0" * 64),
        )
        adapter = self.adapter(overrides={"cp2": [changed]})
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.technical_retries_used, 0)
        self.assertEqual([c[1] for c in adapter.call_trace].count("cp2"), 1)

    def test_p1_04_revision_requires_trigger_evidence(self) -> None:
        log = BuildLogWriter(DeterministicClock())
        record = RevisionRecord(
            before_summary="before",
            after_summary="after",
            change_type="replace",
            trigger_evidence_refs=(),
            affected_refs=("A-001",),
        )
        with self.assertRaises(ValueError):
            log.revision("cp3", record)

    def test_p1_05_supported_alternative_is_retained(self) -> None:
        original = copy.deepcopy(self.example["assertions"]["items"][0])
        original.pop("id")
        original["statement"] = "An evidence-backed alternative interpretation."
        group_fields = {
            "issue": "Which interpretation best explains the amount?",
            "mode": "competing",
            "member_refs": ["A-001", "@alternative"],
            "preferred_ref": "A-001",
            "rationale": "A-001 currently explains more of the available evidence.",
            "unresolved_reason": "The alternative retains direct documentary support.",
            "impact_scope": "Local interpretation only.",
        }
        bundle = CandidateBundle(
            stage="cp3",
            objects=(
                CandidateObject("assertion", "alternative", original),
                CandidateObject("interpretation_group", "choice", group_fields),
            ),
        )
        revision = RevisionRecord(
            before_summary="Only the leading interpretation was explicit.",
            after_summary="The leading and supported alternative are both explicit.",
            change_type="retain_alternative",
            trigger_evidence_refs=("E-002",),
            affected_refs=("A-001",),
            surviving_alternative_refs=("A-007",),
        )
        response = AdapterStageResult(
            stage="cp3", bundle=bundle, revisions=(revision,)
        )
        adapter = self.adapter(
            [self.failed_gate(), self.passed_gate()], [response]
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertIn("A-007", {item["id"] for item in gdu["assertions"]["items"]})
        self.assertEqual(
            gdu["assertions"]["interpretation_groups"][0]["member_refs"],
            ["A-001", "A-007"],
        )

    def test_p1_06_navigation_text_cannot_become_evidence(self) -> None:
        allocator = CanonicalIdAllocator()
        bundle = CandidateBundle(
            stage="cp1",
            objects=(
                CandidateObject(
                    kind="evidence",
                    handle="nav",
                    fields={"modality": "text", "fragments": []},
                    source_authority="navigation",
                ),
            ),
        )
        with self.assertRaises(CandidateValidationError):
            allocator.canonicalize(bundle)

    def test_p1_07_provisional_can_preserve_incomplete_assessment(self) -> None:
        mutation = ObjectMutation(
            operation="downgrade",
            target_ref="A-001",
            replacement_fields={"rationale": "Evidence review remains incomplete."},
        )
        revision = RevisionRecord(
            before_summary="A-001 was assessed as supported.",
            after_summary="A-001 remains present but its assessment is incomplete.",
            change_type="downgrade",
            trigger_evidence_refs=("E-002",),
            affected_refs=("A-001",),
        )
        first = AdapterStageResult(
            stage="cp3",
            bundle=CandidateBundle(stage="cp3", mutations=(mutation,)),
            revisions=(revision,),
        )
        second = AdapterStageResult(
            stage="cp3", bundle=CandidateBundle(stage="cp3")
        )
        adapter = self.adapter(
            [self.failed_gate("1"), self.failed_gate("2"), self.failed_gate("3")],
            [first, second],
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "provisional_complete")
        gdu = json.loads(result.artifact_paths[0].read_text())
        a1 = next(item for item in gdu["assertions"]["items"] if item["id"] == "A-001")
        self.assertFalse(a1["assessment_complete"])
        self.assertNotIn("evidence_status", a1)

    def test_p1_08_logical_time_orders_equal_timestamps(self) -> None:
        class ConstantClock:
            def now(self) -> str:
                return "2026-08-19T16:00:00+08:00"

        log = BuildLogWriter(ConstantClock())
        log.checkpoint("cp1", "completed", "one")
        log.checkpoint("cp2", "completed", "two")
        self.assertEqual([event["logical_time"] for event in log.events], [1, 2])
        self.assertEqual(log.events[0]["timestamp"], log.events[1]["timestamp"])

    def test_p1_09_technical_failure_can_preserve_complete_snapshot(self) -> None:
        adapter = self.adapter(
            overrides={
                "cp6": [
                    TechnicalFailure("fixed_adapter", "cp6 interruption"),
                    TechnicalFailure("fixed_adapter", "cp6 retry interruption"),
                ]
            }
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(len(result.artifact_paths), 3)
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(gdu["manifest"]["gdu_identity"]["status"], "provisional")
        self.assertNotIn("freeze", [e["event_type"] for e in self.load_log(result)])

    def test_p1_10_frozen_log_rejects_later_append(self) -> None:
        log = BuildLogWriter(DeterministicClock())
        log.freeze("1.0.0", self.passed_gate())
        with self.assertRaises(ValueError):
            log.checkpoint("cp6", "passed", "late event")

    def test_mutation_replace_updates_only_in_scope_object(self) -> None:
        mutation = ObjectMutation(
            operation="replace",
            target_ref="A-001",
            replacement_fields={"statement": "A bounded corrected statement."},
        )
        revision = RevisionRecord(
            before_summary="Original A-001.",
            after_summary="Corrected A-001.",
            change_type="replace",
            trigger_evidence_refs=("E-002",),
            affected_refs=("A-001",),
        )
        response = AdapterStageResult(
            stage="cp3",
            bundle=CandidateBundle(stage="cp3", mutations=(mutation,)),
            revisions=(revision,),
        )
        adapter = self.adapter(
            [self.failed_gate(), self.passed_gate()], [response]
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        gdu = json.loads(result.artifact_paths[0].read_text())
        a1 = next(item for item in gdu["assertions"]["items"] if item["id"] == "A-001")
        self.assertEqual(a1["statement"], "A bounded corrected statement.")

    def test_mutation_withdraw_removes_unreferenced_object(self) -> None:
        # First correction promotes an interpretation group; second correction
        # withdraws that unreferenced group without disturbing its members.
        alt_fields = copy.deepcopy(self.example["assertions"]["items"][0])
        alt_fields.pop("id")
        alt_fields["statement"] = "Temporary alternative."
        add_bundle = CandidateBundle(
            stage="cp3",
            objects=(
                CandidateObject("assertion", "alt", alt_fields),
                CandidateObject(
                    "interpretation_group",
                    "group",
                    {
                        "issue": "Temporary issue",
                        "mode": "competing",
                        "member_refs": ["A-001", "@alt"],
                        "preferred_ref": "A-001",
                        "rationale": "Temporary comparison.",
                        "unresolved_reason": "Pending correction.",
                        "impact_scope": "Local.",
                    },
                ),
            ),
        )
        add = AdapterStageResult(
            stage="cp3",
            bundle=add_bundle,
            revisions=(
                RevisionRecord(
                    "before",
                    "after add",
                    "retain_alternative",
                    ("E-002",),
                    ("A-001",),
                    ("A-007",),
                ),
            ),
        )
        gap_two = replace(
            self.failed_gate("withdraw").gaps[0],
            affected_refs=("IG-001",),
        )
        gate_two = StopGateResult(
            coverage="passed",
            evidence="failed",
            stability="passed",
            cross_carrier="passed",
            cross_section="passed",
            negative_boundary="passed",
            gaps=(gap_two,),
            summary="Temporary group should be withdrawn.",
        )
        withdraw = AdapterStageResult(
            stage="cp3",
            bundle=CandidateBundle(
                stage="cp3",
                mutations=(ObjectMutation("withdraw", "IG-001"),),
            ),
            revisions=(
                RevisionRecord(
                    "group present",
                    "group withdrawn",
                    "withdraw",
                    ("E-002",),
                    ("IG-001",),
                ),
            ),
        )
        adapter = self.adapter(
            [self.failed_gate("add"), gate_two, self.passed_gate()],
            [add, withdraw],
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(gdu["assertions"]["interpretation_groups"], [])

    def test_source_wiring_adapter_receives_only_controlled_packets(self) -> None:
        adapter = self.adapter()
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(
            [stage for stage, _ in adapter.packet_trace],
            ["cp1", "cp2", "cp3", "cp4", "cp5", "cp6"],
        )
        for _, packet in adapter.packet_trace:
            self.assertEqual(
                [fragment.page for fragment in packet.pdf_fragments],
                [1, 8, 9, 11],
            )
            self.assertFalse(hasattr(packet, "pdf_path"))

    def test_source_wiring_correction_packet_uses_only_gap_pages(self) -> None:
        adapter = self.adapter(
            [self.failed_gate(), self.passed_gate()], [self.revision_result(1)]
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        correction_packet = adapter.packet_trace[-2][1]
        self.assertEqual(
            [fragment.page for fragment in correction_packet.pdf_fragments],
            [8, 9],
        )

    def test_source_wiring_unauthorized_evidence_is_retried_without_pollution(self) -> None:
        invalid_evidence = CandidateObject(
            kind="evidence",
            handle="bad",
            fields={
                "modality": "text",
                "fragments": [
                    {
                        "page": 1,
                        "locator": "physical-page:1",
                        "excerpt": "Text absent from the authorized PDF packet.",
                        "fragment_sha256": hashlib.sha256(
                            b"Text absent from the authorized PDF packet."
                        ).hexdigest(),
                    }
                ],
            },
        )
        invalid = AdapterStageResult(
            stage="cp1",
            bundle=CandidateBundle(stage="cp1", objects=(invalid_evidence,)),
        )
        valid = AdapterStageResult(
            stage="cp1", bundle=self.valid_bundles()["cp1"]
        )
        adapter = self.adapter(overrides={"cp1": [invalid, valid]})
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.technical_retries_used, 1)
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(gdu["evidence"][0]["id"], "E-001")

    def test_source_wiring_navigation_cannot_authorize_evidence(self) -> None:
        excerpt = "Navigation-only evidence claim."
        invalid = AdapterStageResult(
            stage="cp1",
            bundle=CandidateBundle(
                stage="cp1",
                objects=(
                    CandidateObject(
                        kind="evidence",
                        handle="nav-evidence",
                        fields={
                            "modality": "text",
                            "fragments": [
                                {
                                    "page": 1,
                                    "locator": "navigation",
                                    "excerpt": excerpt,
                                    "fragment_sha256": hashlib.sha256(
                                        excerpt.encode("utf-8")
                                    ).hexdigest(),
                                }
                            ],
                        },
                    ),
                ),
            ),
        )
        adapter = self.adapter(overrides={"cp1": [invalid, invalid]})
        _, result = self.run_builder(
            adapter, navigation_text={1: excerpt}
        )

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.artifact_paths, ())

    def test_source_wiring_reader_failure_uses_global_retry(self) -> None:
        backend = FlakyBuilderPdfBackend(failures=1)
        _, result = self.run_builder(self.adapter(), backend=backend)

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.technical_retries_used, 1)
        self.assertGreaterEqual(backend.extract_calls, 2)

    def test_source_wiring_second_reader_failure_stops_before_adapter(self) -> None:
        backend = FlakyBuilderPdfBackend(failures=2)
        adapter = self.adapter()
        _, result = self.run_builder(adapter, backend=backend)

        self.assertEqual(result.outcome, "technical_failed")
        self.assertEqual(result.technical_retries_used, 1)
        self.assertEqual(adapter.call_trace, [])

    def test_source_wiring_requires_exact_six_stage_plan(self) -> None:
        missing = dict(self.spec.checkpoint_source_requests)
        missing.pop("cp6")
        extra = dict(self.spec.checkpoint_source_requests)
        extra["cp7"] = SourceRequest("extra", ((1, 1),))
        for index, plan in enumerate((missing, extra)):
            with self.subTest(index=index):
                spec = replace(
                    self.spec,
                    output_dir=self.work / f"plan-output-{index}",
                    checkpoint_source_requests=plan,
                )
                adapter = self.adapter()
                _, result = self.run_builder(adapter, spec)
                self.assertEqual(result.outcome, "input_rejected")
                self.assertEqual(adapter.call_trace, [])

    def test_source_wiring_reader_must_point_to_builder_pdf(self) -> None:
        other_pdf = self.work / "other.pdf"
        other_pdf.write_bytes(b"different input")
        reader = SourceReader(
            other_pdf, "other-document", BuilderFixturePdfBackend()
        )
        adapter = self.adapter()
        _, result = self.run_builder(adapter, source_reader=reader)

        self.assertEqual(result.outcome, "input_rejected")
        self.assertEqual(adapter.call_trace, [])

    def test_source_wiring_adapter_cannot_mutate_working_state_directly(self) -> None:
        class MutatingAdapter(FixedUnderstandingAdapter):
            def propose(self, stage, source_packet, public_working_view):  # type: ignore[no-untyped-def]
                if stage == "cp2":
                    public_working_view["physical_structure"].clear()
                return super().propose(stage, source_packet, public_working_view)

        base = self.adapter()
        adapter = MutatingAdapter(
            {
                stage: list(queue)
                for stage, queue in base._proposals.items()  # type: ignore[attr-defined]
            },
            list(base._revisions),  # type: ignore[attr-defined]
        )
        _, result = self.run_builder(adapter)

        self.assertEqual(result.outcome, "frozen_complete")
        gdu = json.loads(result.artifact_paths[0].read_text())
        self.assertEqual(len(gdu["physical_structure"]), 2)

    @unittest.skipUnless(
        REAL_PYPDF_AVAILABLE
        and (ROOT / "research_inputs/pilot_03_litong_2025/paper.pdf").is_file(),
        "real Pilot 03 PDF or pypdf runtime not available",
    )
    def test_source_wiring_real_pilot_pdf_round_trip(self) -> None:
        from gdu.builder_v0.source_reader import PypdfBackend

        pdf = ROOT / "research_inputs/pilot_03_litong_2025/paper.pdf"
        extracted = ROOT / "research_inputs/pilot_03_litong_2025/paper.txt"
        reader = SourceReader(
            pdf, "litong-2025-annual-report", PypdfBackend()
        )
        reader.inspect()
        packet = reader.read(
            SourceRequest(
                "strict real source fixture", ((1, 1), (8, 9), (11, 11))
            )
        )
        by_page = {fragment.page: fragment.excerpt for fragment in packet.pdf_fragments}
        # gdu.example.json is a frozen Schema teaching fixture whose table excerpts
        # are human-normalized summaries. Replace them only in memory with strict
        # continuous PDF text-layer fragments for this SourceReader integration test.
        for evidence in self.example["evidence"]:
            for fragment in evidence["fragments"]:
                fragment["excerpt"] = by_page[fragment["page"]]
                fragment["fragment_sha256"] = hashlib.sha256(
                    fragment["excerpt"].encode("utf-8")
                ).hexdigest()
        spec = replace(
            self.spec,
            source_pdf=pdf,
            extracted_text=extracted,
            output_dir=self.work / "real-pilot-output",
        )
        _, result = self.run_builder(
            self.adapter(), spec=spec, source_reader=reader
        )

        self.assertEqual(result.outcome, "frozen_complete")
        self.assertEqual(result.technical_retries_used, 0)
        self.assertEqual(len(result.artifact_paths), 3)


if __name__ == "__main__":
    unittest.main()
