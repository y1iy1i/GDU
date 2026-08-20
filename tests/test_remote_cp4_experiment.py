from __future__ import annotations

import copy
import unittest

from gdu.builder_v0.types import TechnicalFailure
from scripts.run_remote_cp4_experiment import verify_cp4_semantics


def relation(
    relation_id: str,
    from_ref: str,
    to_ref: str,
    relation_type: str,
) -> tuple[str, dict[str, object]]:
    source = relation_type == "composes"
    fields: dict[str, object] = {
        "id": relation_id,
        "endpoint_level": "assertion",
        "from_ref": from_ref,
        "to_ref": to_ref,
        "relation_type": relation_type,
        "epistemic_origin": (
            "source_attributed" if source else "analytic_interpretation"
        ),
        "assessment_complete": True,
        "evidence_status": "supported",
        "evidence_refs": ["E-003", "E-005"] if source else ["E-003"],
    }
    if source:
        fields["attribution_mode"] = "entailed"
    else:
        fields["basis_assertion_refs"] = [from_ref, to_ref]
    return "relation", fields


def valid_objects() -> list[tuple[str, dict[str, object]]]:
    return [
        relation("R-001", "A-003", "A-001", "composes"),
        relation("R-002", "A-005", "A-006", "supports"),
        relation("R-003", "A-005", "A-007", "supports"),
        relation("R-004", "A-008", "A-006", "limits"),
        relation("R-005", "A-008", "A-007", "limits"),
    ]


class RemoteCp4SemanticAcceptanceTests(unittest.TestCase):
    def test_preregistered_relation_network_passes(self) -> None:
        verify_cp4_semantics(valid_objects())

    def test_required_edge_cannot_be_reversed(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[1][1]["from_ref"] = "A-006"
        objects[1][1]["to_ref"] = "A-005"
        with self.assertRaisesRegex(TechnicalFailure, "edge set"):
            verify_cp4_semantics(objects)

    def test_analytic_basis_must_include_both_endpoints(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[2][1]["basis_assertion_refs"] = ["A-005"]
        with self.assertRaisesRegex(TechnicalFailure, "both endpoints"):
            verify_cp4_semantics(objects)

    def test_composition_requires_both_source_pages(self) -> None:
        objects = copy.deepcopy(valid_objects())
        objects[0][1]["evidence_refs"] = ["E-003"]
        with self.assertRaisesRegex(TechnicalFailure, "source grounding"):
            verify_cp4_semantics(objects)


if __name__ == "__main__":
    unittest.main()
