from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v1 import (  # noqa: E402
    PageElement,
    evidence_manifest_from_elements,
    score_representation_response,
)
from gdu.builder_v0.types import SourceDocumentIdentity  # noqa: E402
from scripts.run_builder_v1_representation_blind_01 import (  # noqa: E402
    GOLD_PATH,
    INPUT_PATH,
    _build_request,
    _load_json,
)


def test_blind_request_is_built_without_gold_and_atoms_match_frozen_gold() -> None:
    input_value = _load_json(INPUT_PATH)
    gold = _load_json(GOLD_PATH)
    manifests, request = _build_request(input_value)

    assert "gold" not in json.dumps(request, ensure_ascii=False).lower()
    assert set(manifests) == {"finance", "pgkd", "standard"}
    gold_by_case = {case["case_id"]: case for case in gold["cases"]}
    for case in input_value["cases"]:
        assert set(case["allowed_atoms"]) == {
            claim["atom"] for claim in gold_by_case[case["case_id"]]["claims"]
        }


def test_exact_valid_candidate_scores_as_correct() -> None:
    identity = SourceDocumentIdentity(
        document_id="finance",
        original_filename="paper.pdf",
        source_sha256="c" * 64,
        pdf_page_count=1,
        extraction_system="fixture-parser",
    )
    manifest = evidence_manifest_from_elements(
        identity,
        [PageElement(1, "经营活动产生的现金流量净额为72,545,781.16元。")],
    )
    block = manifest.blocks[0]
    context = {"document_scope": "finance", "company_scope": "consolidated"}
    response = {
        "cases": [
            {
                "case_id": "finance",
                "proposals": [
                    {
                        "statement": "经营活动产生的现金流量净额为72,545,781.16元。",
                        "atom": "finance_ocf_amount",
                        "semantic_arguments": [
                            {"role": "metric", "value": "经营活动产生的现金流量净额"},
                            {"role": "value", "value": "72,545,781.16元"},
                        ],
                        "polarity": "positive",
                        "epistemic_status": "certain",
                        "normative_force": "none",
                        "context": context,
                        "evidence_quotes": [
                            {"block_id": block.block_id, "quote": block.text}
                        ],
                        "semantic_cues": [],
                        "quantities": [
                            {
                                "surface": "72,545,781.16元",
                                "normalized_value": "72545781.16",
                                "unit": "CNY",
                            }
                        ],
                        "comparison_constraints": [],
                        "attribution": None,
                    }
                ],
            }
        ]
    }
    gold = {
        "cases": [
            {
                "case_id": "finance",
                "claims": [
                    {
                        "atom": "finance_ocf_amount",
                        "polarity": "positive",
                        "epistemic_status": "certain",
                        "normative_force": "none",
                        "context": context,
                        "quantities": [
                            {"normalized_value": "72545781.16", "unit": "CNY"}
                        ],
                        "comparison_constraints": [],
                    }
                ],
            }
        ]
    }

    score = score_representation_response(
        manifests={"finance": manifest},
        response=response,
        gold=gold,
        compiler_id="fixture-compiler",
    )

    assert score["summary"]["exact_precision"] == 1.0
    assert score["summary"]["exact_recall"] == 1.0
    assert score["cases"][0]["correct_atoms"] == ["finance_ocf_amount"]


def test_validator_failure_is_grouped_as_problem_family() -> None:
    identity = SourceDocumentIdentity(
        document_id="doc",
        original_filename="paper.pdf",
        source_sha256="d" * 64,
        pdf_page_count=1,
        extraction_system="fixture-parser",
    )
    manifest = evidence_manifest_from_elements(
        identity, [PageElement(1, "原文金额为10元。")]
    )
    block = manifest.blocks[0]
    response = {
        "cases": [
            {
                "case_id": "case",
                "proposals": [
                    {
                        "statement": "原文金额为99元。",
                        "atom": "amount",
                        "semantic_arguments": [{"role": "value", "value": "99元"}],
                        "polarity": "positive",
                        "epistemic_status": "certain",
                        "normative_force": "none",
                        "context": {"document_scope": "doc"},
                        "evidence_quotes": [
                            {"block_id": block.block_id, "quote": block.text}
                        ],
                        "semantic_cues": [],
                        "quantities": [],
                        "comparison_constraints": [],
                        "attribution": None,
                    }
                ],
            }
        ]
    }
    gold = {
        "cases": [
            {
                "case_id": "case",
                "claims": [
                    {
                        "atom": "amount",
                        "polarity": "positive",
                        "epistemic_status": "certain",
                        "normative_force": "none",
                        "context": {"document_scope": "doc"},
                        "quantities": [{"normalized_value": "10", "unit": "CNY"}],
                        "comparison_constraints": [],
                    }
                ],
            }
        ]
    }

    score = score_representation_response(
        manifests={"case": manifest},
        response=response,
        gold=gold,
        compiler_id="fixture-compiler",
    )

    assert score["summary"]["valid_candidates"] == 0
    assert score["summary"]["problem_family_counts"]["quantity_fidelity"] == 1
