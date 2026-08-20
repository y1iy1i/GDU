from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from gdu.adapter_v1 import OpenAICompatibleRemoteTransport, load_remote_transport_config, sha256_file
from gdu.query_growth_v1 import (
    detect_explanation_gap,
    expand_adjacent_evidence,
    integrate_growth,
    prune_growth_targets,
    validate_growth_response,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "research_inputs/replication_01_lafang_2025/GOLD_GDU_GROWTH_V1.json"
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nodes", "edges"],
    "properties": {
        "nodes": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_id", "role", "mechanism_type", "statement",
                    "evidence_refs", "inventory_direction"
                ],
                "properties": {
                    "candidate_id": {"type": "string", "pattern": "^C[0-9]{2}$"},
                    "role": {"enum": ["mechanism", "bridge"]},
                    "mechanism_type": {
                        "enum": ["noncash_adjustments", "working_capital_adjustments", "combined_explanation"]
                    },
                    "statement": {"type": "string", "minLength": 1},
                    "evidence_refs": {
                        "type": "array", "minItems": 1,
                        "items": {"type": "string", "pattern": "^E-[0-9]+-[A-Z]$"}
                    },
                    "inventory_direction": {"enum": ["increase", "decrease", "not_mentioned"]}
                }
            }
        },
        "edges": {
            "type": "array", "minItems": 2, "maxItems": 8,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["edge_id", "source", "target", "type"],
                "properties": {
                    "edge_id": {"type": "string", "pattern": "^R[0-9]{2}$"},
                    "source": {"type": "string"}, "target": {"type": "string"},
                    "type": {"enum": ["supports", "limits", "conflicts", "composes"]}
                }
            }
        }
    }
}


def _transport() -> tuple[OpenAICompatibleRemoteTransport, str]:
    config_path = ROOT / "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
    config = load_remote_transport_config(
        config_path,
        ROOT / "configs/api/remote-adapter-v1.schema.json",
        sha256_file(config_path),
    )
    return OpenAICompatibleRemoteTransport(
        config, explicit_authorization=True, response_contract=RESPONSE_SCHEMA
    ), config.model


def _request(graph: Mapping[str, Any], gap: Mapping[str, Any], expansion: Mapping[str, Any]) -> dict:
    return {
        "mode": "propose",
        "task": "fill_reasoning_graph_gap_from_bounded_source_evidence",
        "question": graph["question"],
        "gap": gap,
        "instructions": [
            "Use only supplied evidence and surviving observations; do not guess",
            "Create one noncash mechanism, one working-capital mechanism, and one combined bridge",
            "The two mechanism nodes must connect to the bridge with composes edges",
            "Preserve the boundary that positive operating cash flow does not erase loss or prove total cash improvement",
            "Interpret the inventory row using its parenthetical sign rule",
            "Cite every source using exact evidence IDs",
            "Use concise Simplified Chinese"
        ],
        "surviving_nodes": graph["nodes"],
        "expanded_evidence": expansion["evidence"],
        "policy": {"paid_remote_calls_allowed": True, "max_remote_calls": 1}
    }


def run(gold_path: Path) -> dict[str, Any]:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    pruned = prune_growth_targets(gold)
    static_gap = detect_explanation_gap(pruned)
    expansion = expand_adjacent_evidence(
        pruned, ["OBS-PROFIT", "OBS-OCF", "OBS-CASH"], page_radius=1
    )
    request = _request(pruned, static_gap, expansion)
    request_hash = hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    transport, model = _transport()
    response = transport.invoke(request)
    jsonschema.Draft202012Validator(RESPONSE_SCHEMA).validate(response)
    validation = validate_growth_response(response, expansion["evidence"])
    grown_gap = {"decision": "candidate_rejected", "missing_roles": static_gap["missing_roles"]}
    growth_log = None
    if validation["valid"]:
        grown = integrate_growth(pruned, response, validation)
        grown_gap = detect_explanation_gap(grown)
        growth_log = {
            "trigger_question": gold["question"],
            "detected_gap": static_gap,
            "selected_pages": expansion["selected_pages"],
            "new_node_ids": [node["id"] for node in grown["nodes"] if node["id"].startswith("GROW-")],
            "new_edge_ids": [edge["id"] for edge in grown["edges"] if edge["id"].startswith("GROW-R")],
            "recompute_completed": grown_gap["decision"] == "answer_allowed"
        }
    discovery_pass = (
        static_gap["decision"] == "blocked_missing_bridge"
        and expansion["selected_pages"] == [156, 157]
        and validation["valid"]
    )
    answer_readiness_pass = grown_gap["decision"] == "answer_allowed"
    return {
        "experiment": "query-driven-gdu-growth-v1",
        "gold_sha256": sha256_file(gold_path),
        "request_sha256": request_hash,
        "model": model,
        "remote_calls": transport.calls_made,
        "G0_static": static_gap,
        "expansion": {k: v for k, v in expansion.items() if k != "evidence"},
        "candidate_response": response,
        "candidate_validation": validation,
        "G1_grown": grown_gap,
        "growth_log": growth_log,
        "growth_discovery_pass": discovery_pass,
        "answer_readiness_pass": answer_readiness_pass,
        "stage_pass": discovery_pass and answer_readiness_pass
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.gold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GDU_GROWTH_STAGE_PASS" if result["stage_pass"] else "GDU_GROWTH_STAGE_FAIL")
    print(f"OUTPUT {args.output}")
    return 0 if result["stage_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
