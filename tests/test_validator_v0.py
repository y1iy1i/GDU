from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.validator_v0 import (  # noqa: E402
    main,
    validate_file,
    validate_freeze_package,
    validate_schema,
    validate_semantics,
)


class GduV0ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads((ROOT / "gdu.schema.json").read_text())
        cls.example = json.loads((ROOT / "gdu.example.json").read_text())

    def test_frozen_example_passes_schema_and_semantics(self) -> None:
        self.assertEqual(validate_schema(self.example, self.schema), [])
        self.assertEqual(validate_semantics(self.example), [])

    def test_schema_rejects_function_with_two_units(self) -> None:
        value = copy.deepcopy(self.example)
        function = value["assertions"]["items"][-1]
        function["semantic_unit_refs"] = ["U-001", "U-002"]

        codes = {issue.code for issue in validate_schema(value, self.schema)}

        self.assertIn("schema_validation", codes)

    def test_ids_are_globally_unique(self) -> None:
        value = copy.deepcopy(self.example)
        value["evidence"][0]["id"] = "PS-001"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("duplicate_id", codes)

    def test_physical_parent_cycle_is_rejected(self) -> None:
        value = copy.deepcopy(self.example)
        value["physical_structure"][0]["parent_ref"] = "PS-002"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("physical_parent_cycle", codes)
        self.assertIn("physical_root_count", codes)

    def test_page_range_must_stay_inside_document(self) -> None:
        value = copy.deepcopy(self.example)
        value["physical_structure"][1]["page_range"]["end"] = 238

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("page_out_of_bounds", codes)

    def test_function_must_point_back_to_ranked_unit(self) -> None:
        value = copy.deepcopy(self.example)
        function = value["assertions"]["items"][-1]
        function["semantic_unit_refs"] = ["U-missing"]

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("function_back_reference_mismatch", codes)
        self.assertIn("unknown_semantic_unit", codes)

    def test_relation_endpoint_must_match_declared_level(self) -> None:
        value = copy.deepcopy(self.example)
        value["relations"][0]["from_ref"] = "U-001"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("unknown_relation_endpoint", codes)

    def test_preferred_interpretation_must_be_a_member(self) -> None:
        value = copy.deepcopy(self.example)
        value["assertions"]["interpretation_groups"].append(
            {
                "id": "IG-001",
                "issue": "哪一种解释更合适",
                "mode": "competing",
                "member_refs": ["A-001", "A-002"],
                "preferred_ref": "A-003",
                "rationale": "用于验证成员约束。",
                "unresolved_reason": "两个成员仍有来源数据。",
                "impact_scope": "局部利润解释。",
            }
        )

        self.assertEqual(validate_schema(value, self.schema), [])
        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("preferred_not_member", codes)

    def test_fragment_hash_is_recomputed(self) -> None:
        value = copy.deepcopy(self.example)
        value["evidence"][0]["fragments"][0]["excerpt"] += "改"

        codes = {issue.code for issue in validate_semantics(value)}

        self.assertIn("fragment_hash_mismatch", codes)

    def test_frozen_gdu_requires_external_package_files(self) -> None:
        value = copy.deepcopy(self.example)
        value["manifest"]["gdu_identity"]["status"] = "frozen"

        codes = {
            issue.code
            for issue in validate_freeze_package(
                ROOT / "gdu.example.json", value, None, None
            )
        }

        self.assertIn("missing_build_log", codes)
        self.assertIn("missing_artifacts_manifest", codes)

    def test_valid_frozen_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            gdu_path, log_path, artifacts_path = self._write_frozen_package(package)

            issues, setup_error = validate_file(
                gdu_path,
                ROOT / "gdu.schema.json",
                log_path,
                artifacts_path,
            )

            self.assertFalse(setup_error)
            self.assertEqual(issues, [])

    def test_modified_frozen_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            gdu_path, log_path, artifacts_path = self._write_frozen_package(package)
            log_path.write_text(
                log_path.read_text() + json.dumps({"event_type": "technical"}) + "\n"
            )

            issues, setup_error = validate_file(
                gdu_path,
                ROOT / "gdu.schema.json",
                log_path,
                artifacts_path,
            )
            codes = {issue.code for issue in issues}

            self.assertFalse(setup_error)
            self.assertIn("artifact_hash_mismatch", codes)

    def test_cli_exit_zero_for_valid_gdu(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    str(ROOT / "gdu.example.json"),
                    "--schema",
                    str(ROOT / "gdu.schema.json"),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("VALID", output.getvalue())

    def test_cli_exit_one_for_invalid_gdu(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = copy.deepcopy(self.example)
            value["evidence"][0]["fragments"][0]["excerpt"] += "改"
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(value, ensure_ascii=False))
            output = io.StringIO()
            with redirect_stderr(output):
                exit_code = main(
                    [str(path), "--schema", str(ROOT / "gdu.schema.json")]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("fragment_hash_mismatch", output.getvalue())

    def test_cli_exit_two_for_missing_file(self) -> None:
        output = io.StringIO()
        with redirect_stderr(output):
            exit_code = main(
                [
                    str(ROOT / "does-not-exist.json"),
                    "--schema",
                    str(ROOT / "gdu.schema.json"),
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("input_error", output.getvalue())

    def _write_frozen_package(self, package: Path) -> tuple[Path, Path, Path]:
        value = copy.deepcopy(self.example)
        value["manifest"]["gdu_identity"]["status"] = "frozen"
        gdu_path = package / "gdu.json"
        log_path = package / "build_log.jsonl"
        artifacts_path = package / "ARTIFACTS.sha256"
        gdu_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        log_path.write_text(
            json.dumps(
                {
                    "event_id": "EV-001",
                    "event_type": "freeze",
                    "logical_time": 1,
                    "timestamp": "2026-08-19T16:00:00+08:00",
                    "stage": "freeze",
                    "object_refs": [],
                    "rationale": "test fixture",
                }
            )
            + "\n"
        )
        artifacts_path.write_text(
            f"{self._sha256(gdu_path)}  {gdu_path.name}\n"
            f"{self._sha256(log_path)}  {log_path.name}\n"
        )
        return gdu_path, log_path, artifacts_path

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
