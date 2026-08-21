from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from gdu.adapter_v1.remote_transport import (  # noqa: E402
    OpenAICompatibleRemoteTransport,
    load_remote_transport_config,
)
from gdu.adapter_v1.env_file import load_env_file  # noqa: E402
from gdu.builder_v0.types import SourceDocumentIdentity, TechnicalFailure  # noqa: E402
from gdu.builder_v1 import (  # noqa: E402
    EvidenceRelationSpec,
    PageElement,
    TableRegion,
    evidence_manifest_from_elements,
    score_representation_response,
)
from scripts.run_builder_v1_representation_blind_01 import (  # noqa: E402
    CONFIG_PATH,
    CONFIG_SCHEMA_PATH,
    EXPECTED_CONFIG_SHA256,
    PROPOSAL_SCHEMA as V1_PROPOSAL_SCHEMA,
)


INPUT_PATH = ROOT / "research_inputs/builder_v1_representation_blind_02/input.json"
GOLD_PATH = ROOT / "research_inputs/builder_v1_representation_blind_02/gold.json"


def _proposal_schema() -> dict[str, Any]:
    schema = deepcopy(V1_PROPOSAL_SCHEMA)
    proposal = schema["properties"]["cases"]["items"]["properties"]["proposals"]["items"]
    properties = proposal["properties"]
    properties["epistemic_status"]["enum"] = ["certain", "possible", "undetermined"]
    quantity = properties["quantities"]["items"]
    quantity["required"] = [
        "surface",
        "normalized_value",
        "unit",
        "unit_surface",
        "normalization_rule",
    ]
    quantity["properties"]["unit_surface"] = {"type": ["string", "null"]}
    quantity["properties"]["normalization_rule"] = {
        "enum": [
            "identity",
            "strip_grouping",
            "percent_symbol",
            "unit_alias",
            "date_label",
        ]
    }
    comparison = properties["comparison_constraints"]["items"]
    comparison["required"] = [
        "comparison_kind",
        "metric",
        "operator",
        "threshold",
        "unit",
        "surface",
        "reference_metric",
        "reference_set",
    ]
    comparison["properties"]["comparison_kind"] = {
        "enum": ["threshold", "relative", "extremum"]
    }
    comparison["properties"]["operator"]["enum"] = [
        "lt",
        "lte",
        "eq",
        "gte",
        "gt",
        "min",
        "max",
    ]
    comparison["properties"]["threshold"] = {"type": ["string", "null"]}
    comparison["properties"]["reference_metric"] = {"type": ["string", "null"]}
    comparison["properties"]["reference_set"] = {"type": ["string", "null"]}
    return schema


PROPOSAL_SCHEMA = _proposal_schema()


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
            extraction_system=document["extraction_system"],
        )
        locators = {
            element["element_key"]: element["source_locator"]
            for element in document["elements"]
        }
        elements = []
        for element in document["elements"]:
            table_region = element.get("table_region")
            elements.append(
                PageElement(
                    physical_page=element["physical_page"],
                    text=element["text"],
                    block_type=element["block_type"],
                    source_locator=element["source_locator"],
                    table_region=(
                        TableRegion(**table_region) if table_region is not None else None
                    ),
                )
            )
        relation_specs = tuple(
            EvidenceRelationSpec(
                locators[relation["source_key"]],
                locators[relation["target_key"]],
                relation["relation"],
            )
            for relation in document.get("relations", [])
        )
        manifest = evidence_manifest_from_elements(
            identity,
            elements,
            relation_specs=relation_specs,
            extraction_notes=(
                "Held-out fixture frozen before remote generation; no layout facts are supplied outside Evidence Blocks.",
            ),
        )
        manifests[case["case_id"]] = manifest
        cases.append(
            {
                "case_id": case["case_id"],
                "evidence_blocks": [block.as_dict() for block in manifest.blocks],
                "evidence_relations": [
                    relation.as_dict() for relation in manifest.relations
                ],
                "required_context": case["required_context"],
                "allowed_atoms": case["allowed_atoms"],
            }
        )

    request = {
        "mode": "propose",
        "experiment_id": input_value["experiment_id"],
        "task": "Extract every supported atomic proposition represented by the allowed atoms.",
        "instructions": [
            "Use only Evidence Blocks and Evidence Relations; do not use external knowledge.",
            "Return at most one proposal per allowed atom and omit unsupported atoms.",
            "Copy required_context exactly into every proposal for that case.",
            "Every evidence quote must be an exact normalized substring of its Evidence Block.",
            "A proposition polarity describes P versus not-P; it is not a truth or confidence verdict.",
            "Negative numbers, decrease words, and surface 不 do not automatically make proposition polarity negative.",
            "Use epistemic_status=undetermined only when the source explicitly leaves the proposition unresolved.",
            "Annotate every semantic number in the statement as Quantity; avoid adding line numbers or document identifiers to statements.",
            "Quantity surface and unit_surface must be exact source substrings; unit_surface may come from another quoted Evidence Block.",
            "Quantity normalized_value must contain only the canonical numeric value; canonical units are CNY, percent, second, MB, or null.",
            "Choose only an allowed deterministic normalization_rule.",
            "Use comparison_kind=threshold for a fixed value, relative for metric-to-metric comparison, and extremum for min/max over a set.",
            "Threshold comparisons require threshold and Quantity; relative comparisons require reference_metric; extremum comparisons require reference_set.",
            "A non-certain status, normative force, comparison, attribution, or logical negation requires an exact source cue.",
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
        default=ROOT / "research_inputs/builder_v1_representation_blind_02/run_01",
    )
    parser.add_argument("--replay-response", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(ROOT / ".env", allowed_names={"DASHSCOPE_API_KEY"})

    input_value = _load_json(INPUT_PATH)
    manifests, request = _build_request(input_value)
    request_hash = _sha256_json(request)
    if args.dry_run:
        print(f"EXPERIMENT {input_value['experiment_id']}")
        print(f"CASES {len(request['cases'])}")
        print(
            "EVIDENCE_BLOCKS "
            f"{sum(len(case['evidence_blocks']) for case in request['cases'])}"
        )
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

    gold = _load_json(GOLD_PATH)
    score = score_representation_response(
        manifests=manifests,
        response=response,
        gold=gold,
        compiler_id=f"{config.model}:builder-v1-representation-blind-02",
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
