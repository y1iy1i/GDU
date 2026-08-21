from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.types import SourceDocumentIdentity  # noqa: E402
from gdu.builder_v1 import (  # noqa: E402
    ComparisonConstraint,
    PageElement,
    Quantity,
    SemanticArgument,
    SemanticCue,
    compile_representation_seed,
    evidence_manifest_from_elements,
    make_evidence_quote,
    make_representation_candidate,
    representation_candidate_from_proposal,
    validate_representation_candidates,
)
from gdu.logic_v01 import validate_aif_interface  # noqa: E402


class BuilderV1RepresentationTests(unittest.TestCase):
    def manifest(self, text: str, *, document_id: str = "doc"):
        identity = SourceDocumentIdentity(
            document_id=document_id,
            original_filename="paper.pdf",
            source_sha256="b" * 64,
            pdf_page_count=4,
            extraction_system="fixture-parser 1.0",
        )
        return evidence_manifest_from_elements(
            identity, [PageElement(2, text, "paragraph")]
        )

    def finance_candidate(self):
        manifest = self.manifest(
            "2025年经营活动产生的现金流量净额为72,545,781.16元。",
            document_id="finance",
        )
        block = manifest.blocks[0]
        candidate = make_representation_candidate(
            statement="2025年经营活动产生的现金流量净额为72,545,781.16元。",
            atom="operating_cash_flow_amount",
            semantic_arguments=(
                SemanticArgument("metric", "经营活动产生的现金流量净额"),
                SemanticArgument("value", "72,545,781.16元"),
            ),
            polarity="positive",
            context={
                "company_scope": "consolidated",
                "valid_time": {
                    "type": "interval",
                    "start": "2025-01-01",
                    "end": "2025-12-31",
                },
            },
            evidence_quotes=(make_evidence_quote(block.block_id, block.text),),
            quantities=(
                Quantity("2025年", "2025", "year"),
                Quantity("72,545,781.16元", "72545781.16", "CNY"),
            ),
            compiler_id="fixture-compiler-v1",
        )
        return manifest, candidate

    def test_finance_claim_preserves_values_context_and_provenance(self) -> None:
        manifest, candidate = self.finance_candidate()

        errors = validate_representation_candidates(manifest, [candidate])
        graph = compile_representation_seed(manifest, [candidate])

        self.assertEqual(errors, [])
        self.assertEqual(validate_aif_interface(graph), [])
        claim = next(node for node in graph["information_nodes"] if node["kind"] == "claim")
        self.assertEqual(claim["atom"], "operating_cash_flow_amount")
        self.assertEqual(claim["context"]["company_scope"], "consolidated")
        self.assertEqual(claim["provenance"]["quoted_from"], [manifest.blocks[0].block_id])

    def test_possible_method_claim_requires_and_preserves_epistemic_cue(self) -> None:
        manifest = self.manifest(
            "The teacher may generate new training data according to student performance.",
            document_id="pgkd",
        )
        block = manifest.blocks[0]
        candidate = make_representation_candidate(
            statement="The teacher may generate new training data.",
            atom="teacher_generates_training_data",
            semantic_arguments=(
                SemanticArgument("agent", "teacher"),
                SemanticArgument("theme", "new training data"),
            ),
            polarity="positive",
            epistemic_status="possible",
            context={"document_scope": "pgkd", "section_scope": "methods"},
            evidence_quotes=(make_evidence_quote(block.block_id, block.text),),
            semantic_cues=(SemanticCue("epistemic", "may"),),
            compiler_id="fixture-compiler-v1",
        )

        self.assertEqual(validate_representation_candidates(manifest, [candidate]), [])
        without_cue = make_representation_candidate(
            statement=candidate.statement,
            atom=candidate.atom,
            semantic_arguments=candidate.semantic_arguments,
            polarity="positive",
            epistemic_status="possible",
            context=candidate.context,
            evidence_quotes=candidate.evidence_quotes,
            compiler_id=candidate.compiler_id,
        )
        self.assertTrue(
            any(
                error.endswith("noncertain_status_without_cue")
                for error in validate_representation_candidates(manifest, [without_cue])
            )
        )

    def test_source_can_explicitly_leave_a_proposition_undetermined(self) -> None:
        text = "现有资料尚未判定方案甲是否满足上线条件。"
        manifest = self.manifest(text, document_id="undetermined-source")
        block = manifest.blocks[0]
        candidate = make_representation_candidate(
            statement="方案甲是否满足上线条件尚未判定。",
            atom="option_a_meets_deployment_requirement",
            semantic_arguments=(
                SemanticArgument("subject", "方案甲"),
                SemanticArgument("requirement", "上线条件"),
            ),
            polarity="positive",
            epistemic_status="undetermined",
            context={"document_scope": "undetermined-source"},
            evidence_quotes=(make_evidence_quote(block.block_id, text),),
            semantic_cues=(SemanticCue("epistemic", "尚未判定"),),
            compiler_id="fixture-compiler-v1.1",
        )

        self.assertEqual(validate_representation_candidates(manifest, [candidate]), [])

    def test_normative_claim_keeps_force_separate_from_polarity(self) -> None:
        text = "在正常播放速度下，视频内容显式标识持续时间不应少于2秒。"
        manifest = self.manifest(text, document_id="gb45438")
        block = manifest.blocks[0]
        candidate = make_representation_candidate(
            statement=text,
            atom="video_minimum_label_duration",
            semantic_arguments=(
                SemanticArgument("bearer", "视频内容显式标识"),
                SemanticArgument("constraint", "持续时间不少于2秒"),
            ),
            polarity="positive",
            normative_force="obligation",
            context={
                "document_scope": "gb-45438-2025",
                "playback_scope": "normal_speed",
            },
            evidence_quotes=(make_evidence_quote(block.block_id, text),),
            semantic_cues=(
                SemanticCue("normative", "不应"),
                SemanticCue("comparison", "少于"),
            ),
            quantities=(Quantity("2秒", "2", "second"),),
            comparison_constraints=(
                ComparisonConstraint(
                    metric="显式标识持续时间",
                    operator="gte",
                    threshold="2",
                    unit="second",
                    surface="持续时间不应少于2秒",
                ),
            ),
            compiler_id="fixture-compiler-v1",
        )

        self.assertEqual(validate_representation_candidates(manifest, [candidate]), [])
        graph = compile_representation_seed(manifest, [candidate])
        claim = next(node for node in graph["information_nodes"] if node["kind"] == "claim")
        self.assertEqual(claim["normative_force"], "obligation")
        self.assertEqual(claim["polarity"], "positive")

    def test_comparison_language_family_normalizes_to_canonical_operators(self) -> None:
        cases = (
            (
                "持续时间不应少于2秒。",
                "obligation",
                "gte",
                "持续时间",
                "2秒",
                "2",
                "second",
                (SemanticCue("normative", "不应"), SemanticCue("comparison", "少于")),
            ),
            (
                "持续时间应至少达到2秒。",
                "obligation",
                "gte",
                "持续时间",
                "2秒",
                "2",
                "second",
                (SemanticCue("normative", "应"), SemanticCue("comparison", "至少")),
            ),
            (
                "文件大小不得超过10MB。",
                "prohibition",
                "lte",
                "文件大小",
                "10MB",
                "10",
                "MB",
                (SemanticCue("normative", "不得"), SemanticCue("comparison", "超过")),
            ),
            (
                "文件大小至多为10MB。",
                "none",
                "lte",
                "文件大小",
                "10MB",
                "10",
                "MB",
                (SemanticCue("comparison", "至多"),),
            ),
            (
                "文字高度低于5%。",
                "none",
                "lt",
                "文字高度",
                "5%",
                "5",
                "%",
                (SemanticCue("comparison", "低于"),),
            ),
            (
                "文字高度不低于5%。",
                "none",
                "gte",
                "文字高度",
                "5%",
                "5",
                "%",
                (SemanticCue("comparison", "不低于"),),
            ),
        )
        for text, force, operator, metric, surface, value, unit, cues in cases:
            with self.subTest(text=text):
                manifest = self.manifest(text, document_id="comparison-family")
                block = manifest.blocks[0]
                candidate = make_representation_candidate(
                    statement=text,
                    atom="metric_threshold_relation",
                    semantic_arguments=(
                        SemanticArgument("metric", metric),
                        SemanticArgument("threshold", surface),
                    ),
                    polarity="positive",
                    normative_force=force,
                    context={"document_scope": "comparison-fixture"},
                    evidence_quotes=(make_evidence_quote(block.block_id, text),),
                    semantic_cues=cues,
                    quantities=(Quantity(surface, value, unit),),
                    comparison_constraints=(
                        ComparisonConstraint(metric, operator, value, unit, text[:-1]),
                    ),
                    compiler_id="fixture-compiler-v1",
                )

                self.assertEqual(
                    validate_representation_candidates(manifest, [candidate]), []
                )
                self.assertEqual(
                    candidate.comparison_constraints[0].operator, operator
                )

    def test_comparison_cue_and_constraint_must_be_linked_both_ways(self) -> None:
        manifest = self.manifest("文字高度不低于5%。")
        block = manifest.blocks[0]
        without_constraint = make_representation_candidate(
            statement=block.text,
            atom="height_threshold",
            semantic_arguments=(SemanticArgument("metric", "文字高度"),),
            polarity="positive",
            context={"document_scope": "fixture"},
            evidence_quotes=(make_evidence_quote(block.block_id, block.text),),
            semantic_cues=(SemanticCue("comparison", "不低于"),),
            quantities=(Quantity("5%", "5", "%"),),
            compiler_id="fixture-compiler-v1",
        )

        errors = validate_representation_candidates(manifest, [without_constraint])

        self.assertTrue(any(error.endswith("comparison_cue_without_constraint") for error in errors))

    def test_hallucinated_or_unannotated_number_is_rejected(self) -> None:
        manifest, candidate = self.finance_candidate()
        changed = make_representation_candidate(
            statement="2025年经营活动产生的现金流量净额为99元。",
            atom=candidate.atom,
            semantic_arguments=candidate.semantic_arguments,
            polarity="positive",
            context=candidate.context,
            evidence_quotes=candidate.evidence_quotes,
            quantities=(Quantity("2025年", "2025", "year"),),
            compiler_id=candidate.compiler_id,
        )

        errors = validate_representation_candidates(manifest, [changed])

        self.assertTrue(any("statement_number_untraced:99" in error for error in errors))
        self.assertTrue(any("statement_number_unannotated:99" in error for error in errors))

    def test_quote_must_be_an_exact_part_of_the_evidence_block(self) -> None:
        manifest, candidate = self.finance_candidate()
        wrong_quote = make_evidence_quote(
            manifest.blocks[0].block_id, "经营活动产生的现金流量净额为99元"
        )
        changed = make_representation_candidate(
            statement=candidate.statement,
            atom=candidate.atom,
            semantic_arguments=candidate.semantic_arguments,
            polarity="positive",
            context=candidate.context,
            evidence_quotes=(wrong_quote,),
            quantities=candidate.quantities,
            compiler_id=candidate.compiler_id,
        )

        self.assertTrue(
            any(
                "evidence_quote_not_in_block" in error
                for error in validate_representation_candidates(manifest, [changed])
            )
        )

    def test_candidate_tampering_is_detected(self) -> None:
        manifest, candidate = self.finance_candidate()
        changed = replace(candidate, statement="被修改的命题")

        errors = validate_representation_candidates(manifest, [changed])

        self.assertTrue(any(error.endswith("candidate_hash_mismatch") for error in errors))
        self.assertTrue(any(error.endswith("candidate_id_mismatch") for error in errors))

    def test_context_and_predicate_argument_shape_are_required(self) -> None:
        manifest, candidate = self.finance_candidate()
        malformed = make_representation_candidate(
            statement="经营活动产生现金。",
            atom="Operating Cash Flow",
            semantic_arguments=(),
            polarity="positive",
            context={},
            evidence_quotes=candidate.evidence_quotes,
            compiler_id=candidate.compiler_id,
        )

        errors = validate_representation_candidates(manifest, [malformed])

        self.assertTrue(any(error.endswith("atom_invalid") for error in errors))
        self.assertTrue(any(error.endswith("semantic_arguments_missing") for error in errors))
        self.assertTrue(any(error.endswith("context_missing") for error in errors))

    def test_referenced_evidence_is_deduplicated_in_seed_graph(self) -> None:
        manifest, first = self.finance_candidate()
        second = make_representation_candidate(
            statement="经营活动产生的现金流量净额为正。",
            atom="operating_cash_flow_is_positive",
            semantic_arguments=(
                SemanticArgument("metric", "经营活动产生的现金流量净额"),
                SemanticArgument("sign", "正"),
            ),
            polarity="positive",
            context=first.context,
            evidence_quotes=first.evidence_quotes,
            compiler_id=first.compiler_id,
        )

        graph = compile_representation_seed(manifest, [first, second])

        evidence = [node for node in graph["information_nodes"] if node["kind"] == "evidence"]
        claims = [node for node in graph["information_nodes"] if node["kind"] == "claim"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(claims), 2)

    def test_untrusted_model_proposal_gets_local_identity_and_validation(self) -> None:
        manifest, expected = self.finance_candidate()
        proposal = {
            "statement": expected.statement,
            "atom": expected.atom,
            "semantic_arguments": [
                item.as_dict() for item in expected.semantic_arguments
            ],
            "polarity": expected.polarity,
            "epistemic_status": expected.epistemic_status,
            "normative_force": expected.normative_force,
            "context": expected.context,
            "evidence_quotes": [
                {"block_id": item.block_id, "quote": item.quote}
                for item in expected.evidence_quotes
            ],
            "semantic_cues": [],
            "quantities": [item.as_dict() for item in expected.quantities],
            "comparison_constraints": [
                item.as_dict() for item in expected.comparison_constraints
            ],
            "attribution": None,
        }

        parsed = representation_candidate_from_proposal(
            proposal, compiler_id="fixture-compiler-v1"
        )

        self.assertEqual(parsed, expected)
        self.assertEqual(validate_representation_candidates(manifest, [parsed]), [])

    def test_quantity_can_combine_value_and_unit_from_separate_evidence_blocks(self) -> None:
        identity = SourceDocumentIdentity(
            document_id="split-table",
            original_filename="table.pdf",
            source_sha256="c" * 64,
            pdf_page_count=1,
            extraction_system="fixture-parser 1.0",
        )
        manifest = evidence_manifest_from_elements(
            identity,
            [
                PageElement(1, "同比变动（%）", "table"),
                PageElement(1, "经营现金流 -55.06", "table"),
            ],
        )
        header, body = manifest.blocks
        candidate = make_representation_candidate(
            statement="经营现金流同比变动为-55.06%。",
            atom="operating_cash_flow_yoy_change",
            semantic_arguments=(
                SemanticArgument("metric", "经营现金流同比变动"),
                SemanticArgument("value", "-55.06%"),
            ),
            polarity="positive",
            context={"document_scope": "split-table"},
            evidence_quotes=(
                make_evidence_quote(header.block_id, header.text),
                make_evidence_quote(body.block_id, body.text),
            ),
            quantities=(
                Quantity("-55.06", "-55.06", "percent", "%", "identity"),
            ),
            compiler_id="fixture-compiler-v1.1",
        )

        self.assertEqual(validate_representation_candidates(manifest, [candidate]), [])

        altered = make_representation_candidate(
            statement=candidate.statement,
            atom=candidate.atom,
            semantic_arguments=candidate.semantic_arguments,
            polarity="positive",
            context=candidate.context,
            evidence_quotes=candidate.evidence_quotes,
            quantities=(Quantity("-55.06", "99", "percent", "%", "identity"),),
            compiler_id=candidate.compiler_id,
        )
        self.assertTrue(
            any(
                "quantity_normalization_mismatch" in error
                for error in validate_representation_candidates(manifest, [altered])
            )
        )

    def test_relative_and_extremum_comparisons_do_not_require_fake_quantities(self) -> None:
        cases = (
            ComparisonConstraint(
                metric="本期经营现金流",
                operator="lt",
                threshold=None,
                unit="CNY",
                surface="本期低于上期",
                comparison_kind="relative",
                reference_metric="上期经营现金流",
            ),
            ComparisonConstraint(
                metric="验证损失",
                operator="min",
                threshold=None,
                unit=None,
                surface="验证损失最低",
                comparison_kind="extremum",
                reference_set="候选模型",
            ),
        )
        texts = ("本期低于上期。", "返回候选模型中验证损失最低的模型。")
        for index, (constraint, text) in enumerate(zip(cases, texts), 1):
            with self.subTest(kind=constraint.comparison_kind):
                manifest = self.manifest(text, document_id=f"comparison-{index}")
                block = manifest.blocks[0]
                candidate = make_representation_candidate(
                    statement=text,
                    atom=f"comparison_family_{index}",
                    semantic_arguments=(SemanticArgument("metric", constraint.metric),),
                    polarity="positive",
                    context={"document_scope": "comparison-fixture"},
                    evidence_quotes=(make_evidence_quote(block.block_id, text),),
                    semantic_cues=(SemanticCue("comparison", constraint.surface),),
                    comparison_constraints=(constraint,),
                    compiler_id="fixture-compiler-v1.1",
                )

                self.assertEqual(
                    validate_representation_candidates(manifest, [candidate]), []
                )


if __name__ == "__main__":
    unittest.main()
