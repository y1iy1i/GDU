from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.adapter_v1.remote_transport import (  # noqa: E402
    OpenAICompatibleRemoteTransport,
    load_remote_transport_config,
)
from gdu.builder_v0.types import SourceDocumentIdentity, TechnicalFailure  # noqa: E402
from gdu.builder_v1 import (  # noqa: E402
    PageElement,
    evidence_manifest_from_elements,
    score_representation_response,
)


INPUT_PATH = ROOT / "research_inputs/builder_v1_representation_blind_01/input.json"
GOLD_PATH = ROOT / "research_inputs/builder_v1_representation_blind_01/gold.json"
CONFIG_PATH = ROOT / "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
CONFIG_SCHEMA_PATH = ROOT / "configs/api/remote-adapter-v1.schema.json"
EXPECTED_CONFIG_SHA256 = "1b2efddcb24930af8c1b2bc2382ce53bfcde45d6bb5d76ce723a30551dfed617"


PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cases"],
    "properties": {
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id", "proposals"],
                "properties": {
                    "case_id": {"type": "string"},
                    "proposals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "statement",
                                "atom",
                                "semantic_arguments",
                                "polarity",
                                "epistemic_status",
                                "normative_force",
                                "context",
                                "evidence_quotes",
                                "semantic_cues",
                                "quantities",
                                "comparison_constraints",
                                "attribution",
                            ],
                            "properties": {
                                "statement": {"type": "string"},
                                "atom": {"type": "string"},
                                "semantic_arguments": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["role", "value"],
                                        "properties": {
                                            "role": {"type": "string"},
                                            "value": {"type": "string"},
                                        },
                                    },
                                },
                                "polarity": {"enum": ["positive", "negative"]},
                                "epistemic_status": {"enum": ["certain", "possible"]},
                                "normative_force": {
                                    "enum": [
                                        "none",
                                        "obligation",
                                        "prohibition",
                                        "permission",
                                        "recommendation",
                                    ]
                                },
                                "context": {"type": "object", "minProperties": 1},
                                "evidence_quotes": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["block_id", "quote"],
                                        "properties": {
                                            "block_id": {"type": "string"},
                                            "quote": {"type": "string"},
                                        },
                                    },
                                },
                                "semantic_cues": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["kind", "text"],
                                        "properties": {
                                            "kind": {
                                                "enum": [
                                                    "negation",
                                                    "epistemic",
                                                    "normative",
                                                    "comparison",
                                                    "condition",
                                                    "attribution",
                                                ]
                                            },
                                            "text": {"type": "string"},
                                        },
                                    },
                                },
                                "quantities": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["surface", "normalized_value", "unit"],
                                        "properties": {
                                            "surface": {"type": "string"},
                                            "normalized_value": {"type": "string"},
                                            "unit": {"type": ["string", "null"]},
                                        },
                                    },
                                },
                                "comparison_constraints": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": [
                                            "metric",
                                            "operator",
                                            "threshold",
                                            "unit",
                                            "surface",
                                        ],
                                        "properties": {
                                            "metric": {"type": "string"},
                                            "operator": {"enum": ["lt", "lte", "eq", "gte", "gt"]},
                                            "threshold": {"type": "string"},
                                            "unit": {"type": ["string", "null"]},
                                            "surface": {"type": "string"},
                                        },
                                    },
                                },
                                "attribution": {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        }
    },
}


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _build_request(input_value: dict[str, Any]):
    manifests = {}
    cases = []
    for case in input_value["cases"]:
        document = case["document"]
        identity = SourceDocumentIdentity(
            document_id=document["document_id"],
            original_filename=document["original_filename"],
            source_sha256=document["source_sha256"],
            pdf_page_count=document["pdf_page_count"],
            extraction_system="manual-targeted-blind-fixture-v1",
        )
        manifest = evidence_manifest_from_elements(
            identity,
            [
                PageElement(
                    physical_page=document["physical_page"],
                    text=document["text"],
                    block_type="paragraph",
                    source_locator=document["source_locator"],
                )
            ],
            extraction_notes=("Target passage frozen before remote model generation.",),
        )
        manifests[case["case_id"]] = manifest
        cases.append(
            {
                "case_id": case["case_id"],
                "evidence_blocks": [block.as_dict() for block in manifest.blocks],
                "layout_context": document["layout_context"],
                "required_context": case["required_context"],
                "allowed_atoms": case["allowed_atoms"],
            }
        )
    request = {
        "mode": "propose",
        "experiment_id": input_value["experiment_id"],
        "task": "Extract every supported atomic claim represented by the allowed atoms.",
        "instructions": [
            "Use only the supplied Evidence Blocks and layout context; do not use external knowledge.",
            "Return at most one proposal per allowed atom and omit unsupported atoms.",
            "Copy required_context exactly into every proposal for that case.",
            "Each evidence quote must be an exact normalized substring of its Evidence Block.",
            "Use one main predicate per claim and explicit, non-duplicated semantic roles.",
            "Separate polarity, epistemic status, normative force, attribution, quantities, and comparisons.",
            "Annotate every number appearing in a statement as a Quantity grounded in the quote.",
            "Canonical units are CNY, percent, second, MB, or null when no unit applies.",
            "Normalize comparisons as lt, lte, eq, gte, or gt; preserve the exact comparison surface.",
            "A negative polarity, possible status, normative force, comparison, or attribution requires an exact source cue.",
            "Do not infer an obligation from permission, and do not treat surface negation as automatically negative polarity.",
        ],
        "cases": cases,
        "policy": {"paid_remote_calls_allowed": True, "max_remote_calls": 1},
    }
    return manifests, request


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "research_inputs/builder_v1_representation_blind_01/run_01",
    )
    parser.add_argument("--replay-response", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_value = _load_json(INPUT_PATH)
    manifests, request = _build_request(input_value)
    request_hash = _sha256_json(request)
    if args.dry_run:
        print(f"EXPERIMENT {input_value['experiment_id']}")
        print(f"CASES {len(request['cases'])}")
        print(f"EVIDENCE_BLOCKS {sum(len(case['evidence_blocks']) for case in request['cases'])}")
        print(f"REQUEST_SHA256 {request_hash}")
        return 0

    config = load_remote_transport_config(
        CONFIG_PATH, CONFIG_SCHEMA_PATH, EXPECTED_CONFIG_SHA256
    )
    if args.replay_response:
        response = _load_json(args.replay_response)
        calls_made = 0
    else:
        transport = OpenAICompatibleRemoteTransport(
            config,
            explicit_authorization=True,
            response_contract=PROPOSAL_SCHEMA,
        )
        try:
            response = transport.invoke(request)
        except TechnicalFailure as exc:
            print(f"TECHNICAL_STOP {exc.component}: {exc.summary}")
            print(f"REMOTE_CALLS_MADE {transport.calls_made}")
            return 2
        calls_made = transport.calls_made

    # Gold is deliberately loaded only after generation or replay response loading.
    gold = _load_json(GOLD_PATH)
    score = score_representation_response(
        manifests=manifests,
        response=response,
        gold=gold,
        compiler_id=f"{config.model}:builder-v1-representation-blind-01",
    )
    result = {
        "experiment_id": input_value["experiment_id"],
        "model": config.model,
        "provider_id": config.provider_id,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "input_sha256": _sha256_json(input_value),
        "gold_sha256": _sha256_json(gold),
        "request_sha256": request_hash,
        "remote_calls_made": calls_made,
        "response": response,
        "score": score,
    }
    _write_json(args.output_dir / "result.json", result)
    _write_json(args.output_dir / "response.json", response)
    print(json.dumps(score["summary"], ensure_ascii=False, sort_keys=True))
    print(f"OUTPUT {args.output_dir / 'result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
