from __future__ import annotations

import copy
import unittest

from gdu.builder_v0.types import TechnicalFailure
from scripts.run_remote_cp3_experiment import verify_cp3_semantics


def valid_objects() -> list[tuple[str, dict[str, object]]]:
    common = {
        "semantic_unit_refs": ["U-001"],
        "assessment_complete": True,
    }
    return [
        (
            "assertion",
            {
                **common,
                "id": "A-005",
                "kind": "content",
                "statement": "利润增长原因包括算力盈利增加、制造亏损收窄和投资公允价值正向变动。",
                "epistemic_origin": "source_attributed",
                "evidence_status": "supported",
                "evidence_refs": ["E-003"],
            },
        ),
        (
            "assertion",
            {
                **common,
                "id": "A-006",
                "kind": "content",
                "statement": "算力盈利增加和制造亏损收窄构成经营改善方面。",
                "epistemic_origin": "analytic_interpretation",
                "evidence_status": "supported",
                "evidence_refs": ["E-003"],
                "basis_assertion_refs": ["A-005"],
            },
        ),
        (
            "assertion",
            {
                **common,
                "id": "A-007",
                "kind": "content",
                "statement": "对外投资公允价值变动构成投资收益方面。",
                "epistemic_origin": "analytic_interpretation",
                "evidence_status": "supported",
                "evidence_refs": ["E-003", "E-005", "E-006"],
                "basis_assertion_refs": ["A-005", "A-003"],
            },
        ),
        (
            "assertion",
            {
                **common,
                "id": "A-008",
                "kind": "constraint",
                "statement": "现有披露未量化各因素贡献，不能判断哪项贡献最大。",
                "epistemic_origin": "analytic_interpretation",
                "evidence_status": "undetermined",
                "evidence_refs": ["E-003", "E-005", "E-006"],
                "basis_assertion_refs": ["A-005", "A-006", "A-007"],
            },
        ),
        (
            "interpretation_group",
            {
                "id": "IG-001",
                "issue": "利润改善应从哪些方面理解？",
                "mode": "parallel",
                "member_refs": ["A-006", "A-007"],
                "rationale": "两方面均有证据。",
                "unresolved_reason": "相对贡献未量化。",
                "impact_scope": "局部利润解释。",
            },
        ),
    ]


class RemoteCp3SemanticAcceptanceTests(unittest.TestCase):
    def test_preregistered_cp3_candidate_passes(self) -> None:
        verify_cp3_semantics(valid_objects())

    def test_parallel_group_cannot_prefer_one_aspect(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[4][1]["preferred_ref"] = "A-006"
        with self.assertRaisesRegex(TechnicalFailure, "unbiased parallel"):
            verify_cp3_semantics(objects)

    def test_uncertainty_boundary_is_required(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[3][1]["evidence_status"] = "supported"
        with self.assertRaisesRegex(TechnicalFailure, "uncertainty"):
            verify_cp3_semantics(objects)

    def test_unquantified_driver_cannot_be_ranked(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[1][1]["statement"] = "算力盈利增加是最大贡献。"
        with self.assertRaisesRegex(TechnicalFailure, "over-ranked"):
            verify_cp3_semantics(objects)


if __name__ == "__main__":
    unittest.main()
