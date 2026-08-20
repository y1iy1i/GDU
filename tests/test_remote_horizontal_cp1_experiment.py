from __future__ import annotations

import unittest

from gdu.builder_v0.types import (
    CandidateBundle,
    CandidateObject,
    PdfPageFragment,
    TechnicalFailure,
)
from scripts.run_remote_horizontal_cp1_experiment import (
    bind_deterministic_evidence,
    verify_horizontal_structure,
)


class Packet:
    pdf_fragments = []


class BoundaryPacket:
    pdf_fragments = tuple(
        PdfPageFragment(page, f"physical-page:{page}", f"page {page}", "a" * 64)
        for page in (12, 35, 36, 56, 57)
    )


def valid_objects() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "physical_structure",
            {
                "id": "PS-001",
                "parent_ref": None,
                "node_type": "section",
                "original_label": "第三节 管理层讨论与分析",
                "order": 3,
                "page_range": {"start": 12, "end": 36},
                "evidence_refs": ["E-001"],
            },
        ),
        (
            "physical_structure",
            {
                "id": "PS-002",
                "parent_ref": None,
                "node_type": "section",
                "original_label": "第四节 公司治理、环境和社会",
                "order": 4,
                "page_range": {"start": 36, "end": 57},
                "evidence_refs": ["E-002"],
            },
        ),
    ]


class HorizontalCp1Tests(unittest.TestCase):
    def test_expected_overlapping_boundaries_pass(self) -> None:
        verify_horizontal_structure(valid_objects(), Packet())

    def test_non_overlapping_guess_is_rejected(self) -> None:
        objects = valid_objects()
        objects[0][1]["page_range"] = {"start": 12, "end": 35}
        with self.assertRaisesRegex(TechnicalFailure, "incorrect horizontal"):
            verify_horizontal_structure(objects, Packet())

    def test_extra_section_is_rejected(self) -> None:
        objects = valid_objects()
        objects.append(("physical_structure", dict(objects[0][1])))
        with self.assertRaisesRegex(TechnicalFailure, "exactly two"):
            verify_horizontal_structure(objects, Packet())

    def test_evidence_is_replaced_with_exact_source_fragments(self) -> None:
        model_objects = tuple(
            CandidateObject(
                kind="physical_structure",
                handle=f"s{index}",
                fields={key: value for key, value in fields.items() if key != "id"},
            )
            for index, (_, fields) in enumerate(valid_objects())
        )
        bound = bind_deterministic_evidence(
            CandidateBundle(stage="cp1", objects=model_objects), BoundaryPacket()
        )
        evidence = [item for item in bound.objects if item.kind == "evidence"]
        self.assertEqual([item.fields["fragments"][0]["page"] for item in evidence], [12, 36, 57])
        structures = [item for item in bound.objects if item.kind == "physical_structure"]
        self.assertEqual(
            structures[0].fields["evidence_refs"],
            ["@boundary_page_12", "@boundary_page_36"],
        )


if __name__ == "__main__":
    unittest.main()
