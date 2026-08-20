from __future__ import annotations

import copy
import unittest

from scripts.run_remote_cp2_experiment import verify_cp2_semantics
from gdu.builder_v0.types import TechnicalFailure


def valid_objects() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "semantic_unit",
            {
                "id": "U-001",
                "physical_structure_refs": ["PS-002"],
                "evidence_refs": ["E-003", "E-005"],
                "primary_function_ref": "A-004",
            },
        ),
        (
            "assertion",
            {
                "id": "A-001",
                "kind": "content",
                "epistemic_origin": "source_attributed",
                "statement": "净利润为292,589,095.99元。",
                "semantic_unit_refs": ["U-001"],
                "evidence_refs": ["E-003"],
            },
        ),
        (
            "assertion",
            {
                "id": "A-002",
                "kind": "content",
                "epistemic_origin": "source_attributed",
                "statement": "扣非净利润为235,942,443.22元。",
                "semantic_unit_refs": ["U-001"],
                "evidence_refs": ["E-003"],
            },
        ),
        (
            "assertion",
            {
                "id": "A-003",
                "kind": "content",
                "epistemic_origin": "source_attributed",
                "statement": "非经常性损益为56,646,652.77元。",
                "semantic_unit_refs": ["U-001"],
                "evidence_refs": ["E-005"],
            },
        ),
        (
            "assertion",
            {
                "id": "A-004",
                "kind": "function",
                "epistemic_origin": "analytic_interpretation",
                "statement": "帮助读者理解利润构成。",
                "semantic_unit_refs": ["U-001"],
                "evidence_refs": ["E-003", "E-005"],
                "basis_assertion_refs": ["A-001", "A-002", "A-003"],
            },
        ),
    ]


class RemoteCp2SemanticAcceptanceTests(unittest.TestCase):
    def test_preregistered_cp2_candidate_passes(self) -> None:
        verify_cp2_semantics(valid_objects())

    def test_primary_function_must_be_a_function_assertion(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[0][1]["primary_function_ref"] = "A-001"
        with self.assertRaisesRegex(TechnicalFailure, "primary function"):
            verify_cp2_semantics(objects)

    def test_all_three_preregistered_facts_are_required(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[2][1]["statement"] = "缺少预登记金额。"
        with self.assertRaisesRegex(TechnicalFailure, "235,942,443.22"):
            verify_cp2_semantics(objects)

    def test_primary_function_requires_all_fact_bases(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[4][1]["basis_assertion_refs"] = ["A-001", "A-002"]
        with self.assertRaisesRegex(TechnicalFailure, "all preregistered facts"):
            verify_cp2_semantics(objects)


if __name__ == "__main__":
    unittest.main()
