from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.run_builder_v1_representation_blind_02 import (  # noqa: E402
    GOLD_PATH,
    INPUT_PATH,
    PROPOSAL_SCHEMA,
    _build_request,
    _load_json,
)


def test_blind_02_request_excludes_gold_and_free_layout_context() -> None:
    input_value = _load_json(INPUT_PATH)
    gold = _load_json(GOLD_PATH)
    manifests, request = _build_request(input_value)

    serialized = json.dumps(request, ensure_ascii=False).lower()
    assert "gold" not in serialized
    assert "layout_context" not in serialized
    assert set(manifests) == {
        "finance_table",
        "pgkd_algorithm",
        "standard_metadata",
        "comparison_control",
    }
    assert sum(len(manifest.blocks) for manifest in manifests.values()) == 11
    assert sum(len(case["claims"]) for case in gold["cases"]) == 13


def test_blind_02_atoms_match_frozen_gold() -> None:
    input_value = _load_json(INPUT_PATH)
    gold = _load_json(GOLD_PATH)
    gold_by_case = {case["case_id"]: case for case in gold["cases"]}

    for case in input_value["cases"]:
        assert set(case["allowed_atoms"]) == {
            claim["atom"] for claim in gold_by_case[case["case_id"]]["claims"]
        }


def test_blind_02_schema_exposes_new_problem_family_fields() -> None:
    proposal = PROPOSAL_SCHEMA["properties"]["cases"]["items"]["properties"][
        "proposals"
    ]["items"]["properties"]
    assert "undetermined" in proposal["epistemic_status"]["enum"]
    assert "unit_surface" in proposal["quantities"]["items"]["required"]
    comparison = proposal["comparison_constraints"]["items"]
    assert "comparison_kind" in comparison["required"]
    assert {"min", "max"} <= set(comparison["properties"]["operator"]["enum"])


def test_finance_table_context_is_inside_evidence_manifest() -> None:
    input_value = _load_json(INPUT_PATH)
    manifests, _ = _build_request(input_value)
    manifest = manifests["finance_table"]

    assert len(manifest.relations) == 3
    assert {block.table_region.region_kind for block in manifest.blocks} == {
        "header",
        "unit_note",
        "body",
    }
    assert {relation.relation for relation in manifest.relations} == {
        "qualifies",
        "defines_unit",
    }
