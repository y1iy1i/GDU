from __future__ import annotations

import unittest

from scripts.run_external_replication_minimal_gdu import (
    bind_evidence,
    normalize_builder_response,
)
from scripts.run_gdu_vs_chunk_rag_benchmark import Chunk


class MinimalEvidenceBindingTests(unittest.TestCase):
    def test_model_labels_are_replaced_by_canonical_exact_evidence(self) -> None:
        selected = {"P5-C1": Chunk("P5-C1", "原始证据")}
        response = {
            "summary": "测试",
            "assertions": [
                {
                    "temp_id": "N01",
                    "statement": "测试判断",
                    "role": "fact",
                    "epistemic_source": "source_statement",
                    "evidence_labels": ["P5-C1"],
                }
            ],
        }
        result = bind_evidence(response, selected)
        self.assertEqual(result["assertions"][0]["evidence_refs"], ["E-001"])
        self.assertEqual(result["evidence"][0]["physical_page"], 5)
        self.assertEqual(result["evidence"][0]["text"], "原始证据")
        self.assertEqual(len(result["evidence"][0]["sha256"]), 64)

    def test_epistemic_value_in_role_slot_is_normalized(self) -> None:
        response = {
            "summary": "测试",
            "assertions": [
                {
                    "temp_id": "N01",
                    "statement": "审计意见",
                    "role": "auditor_statement",
                    "epistemic_source": "source_statement",
                    "evidence_labels": ["P61-C1"],
                }
            ],
        }
        normalized = normalize_builder_response(response)
        self.assertEqual(normalized["assertions"][0]["role"], "fact")
        self.assertEqual(
            normalized["assertions"][0]["epistemic_source"], "auditor_statement"
        )


if __name__ == "__main__":
    unittest.main()
