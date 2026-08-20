from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from gdu.builder_v0.cli import main
from gdu.builder_v0.config import ConfigError, _source_request, load_builder_config
from gdu.builder_v0.fixture_adapter import GduFixtureAdapter
from gdu.builder_v0.types import PdfPageFragment, SourcePacket


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "builder-run-pilot03.example.json"
CONFIG_SCHEMA_PATH = ROOT / "builder-run-v0.schema.json"
HAS_PYPDF = importlib.util.find_spec("pypdf") is not None
HAS_PILOT03 = all(
    path.is_file()
    for path in (
        ROOT / "research_inputs/pilot_03_litong_2025/paper.pdf",
        ROOT / "research_inputs/pilot_03_litong_2025/paper.txt",
    )
)


class BuilderConfigSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(
            cls.schema, format_checker=jsonschema.FormatChecker()
        )

    def assert_invalid(self, value: dict) -> None:
        self.assertTrue(list(self.validator.iter_errors(value)))

    @unittest.skipUnless(HAS_PILOT03, "local Pilot 03 source files are unavailable")
    def test_example_config_loads_and_resolves_all_six_checkpoints(self) -> None:
        loaded = load_builder_config(CONFIG_PATH)
        self.assertEqual("pilot03-fixed-fixture-replay-v0", loaded.spec.run_id)
        self.assertEqual("2026-08-20T00:00:00+08:00", loaded.run_timestamp)
        self.assertEqual(
            {"cp1", "cp2", "cp3", "cp4", "cp5", "cp6"},
            set(loaded.spec.checkpoint_source_requests),
        )
        self.assertTrue(loaded.spec.source_pdf.is_absolute())
        self.assertEqual("pypdf 6.16.1", loaded.spec.expected_extraction_system)
        self.assertEqual("gdu.example.json", loaded.fixture_gdu_path.name)

    def test_schema_rejects_parent_path_escape(self) -> None:
        value = copy.deepcopy(self.config)
        value["source"]["pdf"] = "../paper.pdf"
        self.assert_invalid(value)

    def test_schema_rejects_absolute_path(self) -> None:
        value = copy.deepcopy(self.config)
        value["source"]["pdf"] = "/tmp/paper.pdf"
        self.assert_invalid(value)

    def test_schema_requires_exactly_six_checkpoint_requests(self) -> None:
        value = copy.deepcopy(self.config)
        del value["checkpoint_source_requests"]["cp6"]
        self.assert_invalid(value)

    def test_schema_rejects_loosened_frozen_limits(self) -> None:
        value = copy.deepcopy(self.config)
        value["limits"]["max_semantic_corrections"] = 3
        self.assert_invalid(value)

    def test_schema_requires_a_valid_fixed_run_timestamp(self) -> None:
        value = copy.deepcopy(self.config)
        value["run_timestamp"] = "now"
        self.assert_invalid(value)

    def test_loader_rejects_reversed_page_range(self) -> None:
        with self.assertRaisesRegex(ConfigError, "ends before"):
            _source_request(
                {
                    "purpose": "invalid range",
                    "page_ranges": [{"start": 5, "end": 4}],
                    "modalities": ["text"],
                    "locator_hints": [],
                }
            )


class FixtureAdapterTests(unittest.TestCase):
    def test_cp1_replaces_non_contiguous_table_summary_with_page_text(self) -> None:
        fixture = json.loads((ROOT / "gdu.example.json").read_text(encoding="utf-8"))
        fragments = tuple(
            PdfPageFragment(
                page=page,
                locator=f"physical-page:{page}",
                excerpt=f"authoritative full page text for page {page}",
                fragment_sha256=hashlib.sha256(
                    f"authoritative full page text for page {page}".encode("utf-8")
                ).hexdigest(),
            )
            for page in (1, 8, 9, 11)
        )
        packet = SourcePacket(
            source_document_id="litong-2025-annual-report",
            request_identity="request",
            pdf_fragments=fragments,
        )
        adapter = GduFixtureAdapter(fixture, ("model", "none", "a" * 64))

        result = adapter.propose("cp1", packet, {})

        self.assertIsNotNone(result.bundle)
        evidence = [item for item in result.bundle.objects if item.kind == "evidence"]
        page_nine = next(
            fragment
            for item in evidence
            for fragment in item.fields["fragments"]
            if fragment["page"] == 9
        )
        self.assertEqual(
            "authoritative full page text for page 9", page_nine["excerpt"]
        )
        self.assertEqual(
            hashlib.sha256(page_nine["excerpt"].encode("utf-8")).hexdigest(),
            page_nine["fragment_sha256"],
        )
        physical = [
            item for item in result.bundle.objects if item.kind == "physical_structure"
        ]
        self.assertTrue(physical[0].fields["evidence_refs"][0].startswith("@"))


@unittest.skipUnless(
    HAS_PYPDF and HAS_PILOT03,
    "pypdf or local Pilot 03 source files are unavailable",
)
class BuilderCliIntegrationTests(unittest.TestCase):
    def test_pilot03_cli_builds_a_frozen_three_file_package(self) -> None:
        tmp_parent = ROOT / "tmp"
        tmp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_parent) as temporary:
            output = Path(temporary) / "output"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run",
                        "--config",
                        str(CONFIG_PATH),
                        "--output-dir",
                        str(output),
                    ]
                )
            result = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code, stderr.getvalue())
            self.assertEqual("frozen_complete", result["outcome"])
            self.assertEqual(0, result["semantic_corrections_used"])
            self.assertEqual(0, result["technical_retries_used"])
            self.assertEqual(
                {"gdu.json", "build_log.jsonl", "ARTIFACTS.sha256"},
                {path.name for path in output.iterdir()},
            )

    def test_same_config_produces_byte_identical_packages(self) -> None:
        tmp_parent = ROOT / "tmp"
        tmp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_parent) as temporary:
            outputs = [Path(temporary) / name for name in ("first", "second")]
            for output in outputs:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    exit_code = main(
                        [
                            "run",
                            "--config",
                            str(CONFIG_PATH),
                            "--output-dir",
                            str(output),
                        ]
                    )
                self.assertEqual(0, exit_code)
            for filename in ("gdu.json", "build_log.jsonl", "ARTIFACTS.sha256"):
                self.assertEqual(
                    (outputs[0] / filename).read_bytes(),
                    (outputs[1] / filename).read_bytes(),
                    filename,
                )


if __name__ == "__main__":
    unittest.main()
