from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from gdu.reasoning_graph_v1 import (
    answer_gate,
    apply_approved_repair,
    audit_path,
    propose_repairs,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = (
    ROOT / "research_inputs/replication_01_lafang_2025/GOLD_GDU_SLICE_V1.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(graph_path: Path) -> dict:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    baseline_path = ["A-CF-01", "A-CF-02", "A-CF-03", "A-CF-04", "A-CF-05"]
    baseline_gate = answer_gate(audit_path(graph, baseline_path))

    faulty = deepcopy(graph)
    inventory = next(node for node in faulty["nodes"] if node["id"] == "A-CF-03")
    inventory["statement"] = "2025年拉芳家化存货减少2182144.36元"
    inventory["structured_claim"]["direction"] = "decrease"
    faulty_gate = answer_gate(audit_path(faulty, baseline_path))
    issues = audit_path(faulty, baseline_path)
    proposals = propose_repairs(faulty, issues)
    repaired = apply_approved_repair(faulty, proposals[0], approved=True)
    repaired_path = ["A-CF-01", "A-CF-02", "A-CF-03-v2", "A-CF-04", "A-CF-05"]
    repaired_gate = answer_gate(audit_path(repaired, repaired_path))

    conflicted = deepcopy(graph)
    conflicted["nodes"].append(
        {
            "id": "A-CF-ALT",
            "statement": "存货方向存在一个尚未核验的相反解释",
            "role": "interpretation",
            "status": "active",
            "version": 1,
            "evidence_refs": ["E-156-INV"],
        }
    )
    conflicted["edges"].append(
        {
            "id": "R-CF-CONFLICT",
            "source": "A-CF-03",
            "target": "A-CF-ALT",
            "type": "conflicts",
        }
    )
    conflict_gate = answer_gate(audit_path(conflicted, ["A-CF-03", "A-CF-ALT"]))

    return {
        "experiment": "reasoning-graph-self-repair-v1",
        "graph_sha256": sha256_file(graph_path),
        "remote_model_calls": 0,
        "cases": {
            "validated_graph": baseline_gate,
            "injected_sign_error": faulty_gate,
            "repair_proposal": proposals[0],
            "approved_versioned_repair": {
                "gate": repaired_gate,
                "old_node_status": next(
                    node["status"] for node in repaired["nodes"] if node["id"] == "A-CF-03"
                ),
                "new_node_id": "A-CF-03-v2",
                "new_node_status": next(
                    node["status"]
                    for node in repaired["nodes"]
                    if node["id"] == "A-CF-03-v2"
                ),
                "repair_log": repaired["repair_log"],
            },
            "unresolved_explicit_conflict": conflict_gate,
        },
        "stage_pass": all(
            (
                baseline_gate["decision"] == "answer_allowed",
                faulty_gate["decision"] == "blocked_repair_required",
                repaired_gate["decision"] == "answer_allowed",
                conflict_gate["decision"] == "answer_with_uncertainty",
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SELF_REPAIR_STAGE_PASS" if result["stage_pass"] else "SELF_REPAIR_STAGE_FAIL")
    print(f"OUTPUT {args.output}")
    return 0 if result["stage_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

