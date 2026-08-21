from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.types import SourceDocumentIdentity  # noqa: E402
from gdu.builder_v1 import (  # noqa: E402
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
                error.endswith("possible_status_without_cue")
                for error in validate_representation_candidates(manifest, [without_cue])
            )
        )

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
            semantic_cues=(SemanticCue("normative", "不应"),),
            quantities=(Quantity("2秒", "2", "second"),),
            compiler_id="fixture-compiler-v1",
        )

        self.assertEqual(validate_representation_candidates(manifest, [candidate]), [])
        graph = compile_representation_seed(manifest, [candidate])
        claim = next(node for node in graph["information_nodes"] if node["kind"] == "claim")
        self.assertEqual(claim["normative_force"], "obligation")
        self.assertEqual(claim["polarity"], "positive")

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
            "attribution": None,
        }

        parsed = representation_candidate_from_proposal(
            proposal, compiler_id="fixture-compiler-v1"
        )

        self.assertEqual(parsed, expected)
        self.assertEqual(validate_representation_candidates(manifest, [parsed]), [])


if __name__ == "__main__":
    unittest.main()
