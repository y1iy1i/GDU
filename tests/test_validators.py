from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.validators import validate_semantics  # noqa: E402


class GduValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schemas" / "gdu-v0.1.schema.json").read_text()
        )
        cls.example = json.loads(
            (ROOT / "examples" / "gdu-minimal.example.json").read_text()
        )

    def test_minimal_example_passes_schema_and_semantics(self) -> None:
        jsonschema.validate(self.example, self.schema)
        self.assertEqual(validate_semantics(self.example), [])

    def test_explicit_claim_requires_source_grounded_support(self) -> None:
        value = copy.deepcopy(self.example)
        value["evidence_links"] = [
            link
            for link in value["evidence_links"]
            if link["claim_id"] != "claim.demo.purpose"
        ]

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("missing_source_evidence", codes)

    def test_fact_cannot_use_genre_prior_as_its_only_evidence(self) -> None:
        value = copy.deepcopy(self.example)
        claim = value["claims"][0]
        claim["claim_type"] = "fact"
        value["document_model"]["purpose_claim_ids"] = []
        link = value["evidence_links"][0]
        link["support_mode"] = "genre_prior"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("fact_without_textual_evidence", codes)

    def test_dangling_source_reference_is_rejected(self) -> None:
        value = copy.deepcopy(self.example)
        value["evidence_links"][0]["source_unit_ids"] = ["src.missing"]

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("unknown_source_unit", codes)

    def test_ids_must_be_unique_across_object_types(self) -> None:
        value = copy.deepcopy(self.example)
        value["views"][0]["view_id"] = "claim.demo.purpose"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("duplicate_id", codes)

    def test_inferred_section_requires_boundary_rationale(self) -> None:
        value = copy.deepcopy(self.example)
        section = value["document_model"]["sections"][0]
        section["boundary_origin"] = "inferred"
        section["boundary_rationale"] = ""

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("missing_boundary_rationale", codes)

    def test_section_parent_cycle_is_rejected(self) -> None:
        value = copy.deepcopy(self.example)
        first = value["document_model"]["sections"][0]
        second = copy.deepcopy(first)
        first["parent_section_id"] = "section.demo.2"
        second["section_id"] = "section.demo.2"
        second["parent_section_id"] = "section.demo.1"
        second["order"] = 1
        value["document_model"]["sections"].append(second)

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("section_parent_cycle", codes)

    def test_view_cannot_derive_from_itself(self) -> None:
        value = copy.deepcopy(self.example)
        view = value["views"][0]
        view["derived_from_ids"] = [view["view_id"]]

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("unknown_view_input", codes)


if __name__ == "__main__":
    unittest.main()
