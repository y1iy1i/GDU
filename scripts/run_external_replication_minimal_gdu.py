from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.types import TechnicalFailure
from scripts.run_gdu_vs_chunk_rag_benchmark import (
    RESPONSE_SCHEMA,
    Chunk,
    chunk_pdf_text,
    retrieve,
)


ROOT = Path(__file__).resolve().parents[1]
PDF_SHA256 = "f3998163e47f7708c0613fd8e178ce94af04c2dda306bb548229739b451a4b23"
TEXT_SHA256 = "6294caadae1f53f6d7512b093421429b9f944d7483c9c360d6fda2153f1c913a"
QUESTIONS = (
    ("Q1", "报告期经营变化的核心主线是什么？不同业务、品牌或渠道的表现是否一致？"),
    ("Q2", "利润变化由哪些经营性与非经常性因素共同造成？不能把哪些因素混为一谈？"),
    ("Q3", "经营现金流与利润是否指向相同的经营质量结论？还需结合哪些资产、减值或周转信息？"),
    ("Q4", "客户、渠道、品牌或供应商集中度披露与风险叙述之间有什么关系或口径边界？"),
    ("Q5", "管理层未来计划是否代表未来业绩已经得到保证？主要限制条件是什么？"),
    ("Q6", "报告中是否存在必须并列保留的表格、勾选项、时间点或叙述张力？没有充分证据时不得强行制造冲突。"),
)
BUILDER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "assertions"],
    "properties": {
        "summary": {"type": "string", "minLength": 1},
        "assertions": {
            "type": "array",
            "minItems": 12,
            "maxItems": 30,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "temp_id",
                    "statement",
                    "role",
                    "epistemic_source",
                    "evidence_labels",
                ],
                "properties": {
                    "temp_id": {"type": "string", "pattern": "^N[0-9]{2}$"},
                    "statement": {"type": "string", "minLength": 1},
                    "role": {
                        "enum": ["fact", "interpretation", "limitation", "conflict", "missing"]
                    },
                    "epistemic_source": {
                        "enum": ["source_statement", "builder_analysis", "auditor_statement"]
                    },
                    "evidence_labels": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "pattern": "^P[0-9]+-C[0-9]+$"},
                    },
                },
            },
        },
    },
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remote_transport(response_schema: Mapping[str, Any]) -> tuple[OpenAICompatibleRemoteTransport, str]:
    config_path = ROOT / "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
    config_hash = sha256_file(config_path)
    remote = load_remote_transport_config(
        config_path, ROOT / "configs/api/remote-adapter-v1.schema.json", config_hash
    )
    return (
        OpenAICompatibleRemoteTransport(
            remote, explicit_authorization=True, response_contract=response_schema
        ),
        remote.model,
    )


def source_chunks(text_path: Path) -> list[Chunk]:
    if file_sha256(text_path) != TEXT_SHA256:
        raise TechnicalFailure("external_replication", "text SHA-256 mismatch")
    return chunk_pdf_text(text_path.read_text(encoding="utf-8"))


def build_request(chunks: list[Chunk]) -> tuple[dict[str, Any], dict[str, Chunk]]:
    selected: dict[str, Chunk] = {}
    retrieval_log = []
    for question_id, question in QUESTIONS:
        matches = retrieve(chunks, question, budget=7200)
        retrieval_log.append(
            {
                "question_id": question_id,
                "question": question,
                "labels": [item.label for item in matches],
            }
        )
        selected.update({item.label: item for item in matches})
    request = {
        "task": "build_minimal_traceable_document_assertions",
        "document": "拉芳家化股份有限公司2025年年度报告",
        "instructions": [
            "Use only supplied source_chunks; no external knowledge",
            "Create a compact set of reusable assertions that supports all six research questions",
            "Separate source facts, builder analysis, auditor statements, limitations, conflicts, and important missing information",
            "Do not manufacture a conflict when two statements have different scopes",
            "Do not copy full source text; cite exact source chunk labels and let code bind evidence",
            "Every numerical statement must cite a chunk containing that exact number",
            "Plans and forecasts are not completed results or guarantees",
            "Use concise Simplified Chinese",
        ],
        "research_questions": [
            {"question_id": question_id, "question": question}
            for question_id, question in QUESTIONS
        ],
        "source_chunks": [
            {"label": label, "text": selected[label].text} for label in sorted(selected)
        ],
        "retrieval_log": retrieval_log,
        "policy": {"paid_remote_calls_allowed": True, "max_remote_calls": 1},
    }
    return request, selected


def bind_evidence(response: Mapping[str, Any], selected: Mapping[str, Chunk]) -> dict[str, Any]:
    temp_ids = [item["temp_id"] for item in response["assertions"]]
    if len(temp_ids) != len(set(temp_ids)):
        raise TechnicalFailure("external_replication", "duplicate assertion temp_id")
    referenced = []
    for item in response["assertions"]:
        for label in item["evidence_labels"]:
            if label not in selected:
                raise TechnicalFailure("external_replication", f"unknown evidence label: {label}")
            if label not in referenced:
                referenced.append(label)
    evidence_ids = {label: f"E-{index:03d}" for index, label in enumerate(referenced, 1)}
    evidence = []
    for label in referenced:
        chunk = selected[label]
        page_match = re.match(r"P(\d+)-C\d+", label)
        if page_match is None:
            raise TechnicalFailure("external_replication", f"invalid page label: {label}")
        evidence.append(
            {
                "id": evidence_ids[label],
                "source_label": label,
                "physical_page": int(page_match.group(1)),
                "text": chunk.text,
                "sha256": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            }
        )
    assertions = []
    for index, item in enumerate(response["assertions"], 1):
        assertions.append(
            {
                "id": f"A-{index:03d}",
                "statement": item["statement"],
                "role": item["role"],
                "epistemic_source": item["epistemic_source"],
                "evidence_refs": [evidence_ids[label] for label in item["evidence_labels"]],
                "status": "provisional",
            }
        )
    return {
        "format": "minimal-gdu-nodes-v1",
        "document_id": "lafang-2025-annual-report",
        "source_pdf_sha256": PDF_SHA256,
        "source_text_sha256": TEXT_SHA256,
        "builder_summary": response["summary"],
        "assertions": assertions,
        "evidence": evidence,
    }


def normalize_builder_response(response: Mapping[str, Any]) -> dict[str, Any]:
    """Repair a narrow category-slot confusion without changing statement content."""
    normalized = json.loads(json.dumps(response, ensure_ascii=False))
    epistemic_values = {"source_statement", "builder_analysis", "auditor_statement"}
    role_values = {"fact", "interpretation", "limitation", "conflict", "missing"}
    for item in normalized.get("assertions", []):
        role = item.get("role")
        epistemic = item.get("epistemic_source")
        if role in epistemic_values:
            item["epistemic_source"] = role
            item["role"] = "fact" if role != "builder_analysis" else "interpretation"
        elif epistemic in role_values:
            item["role"] = epistemic
            item["epistemic_source"] = "source_statement"
    return normalized


def build_minimal(text_path: Path, output: Path) -> int:
    chunks = source_chunks(text_path)
    request, selected = build_request(chunks)
    transport, model = remote_transport(BUILDER_RESPONSE_SCHEMA)
    raw_response = transport.invoke(request)
    response = normalize_builder_response(raw_response)
    try:
        jsonschema.Draft202012Validator(BUILDER_RESPONSE_SCHEMA).validate(response)
    except jsonschema.ValidationError:
        rejected = output.with_suffix(".rejected.json")
        rejected.write_text(
            json.dumps(raw_response, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise
    minimal = bind_evidence(response, selected)
    minimal["model"] = model
    minimal["calls_made"] = transport.calls_made
    minimal["build_context_sha256"] = hashlib.sha256(
        json.dumps(request["source_chunks"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(minimal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MINIMAL_GDU_BUILD_OK")
    print(f"ASSERTIONS {len(minimal['assertions'])}")
    print(f"EVIDENCE {len(minimal['evidence'])}")
    print(f"OUTPUT {output}")
    return 0


def raw_answer_tasks(chunks: list[Chunk]) -> list[dict[str, Any]]:
    tasks = []
    for question_id, question in QUESTIONS:
        selected = retrieve(chunks, question, budget=7200)
        tasks.append(
            {
                "question_id": question_id,
                "question": question,
                "retrieved_context": [
                    {"label": item.label, "text": item.text} for item in selected
                ],
                "context_characters": sum(len(item.text) for item in selected),
            }
        )
    return tasks


def minimal_answer_tasks(minimal: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = {item["id"]: item for item in minimal["evidence"]}
    node_chunks = [
        Chunk(
            item["id"],
            (
                f"判断 {item['id']}｜角色 {item['role']}｜认识来源 {item['epistemic_source']}\n"
                f"{item['statement']}\n证据引用：{', '.join(item['evidence_refs'])}"
            ),
        )
        for item in minimal["assertions"]
    ]
    tasks = []
    for question_id, question in QUESTIONS:
        selected_nodes = retrieve(node_chunks, question, budget=3000)
        contexts = [{"label": item.label, "text": item.text} for item in selected_nodes]
        used = sum(len(item["text"]) for item in contexts)
        refs = []
        selected_ids = {item.label for item in selected_nodes}
        for assertion in minimal["assertions"]:
            if assertion["id"] not in selected_ids:
                continue
            for ref in assertion["evidence_refs"]:
                if ref not in refs:
                    refs.append(ref)
        for ref in refs:
            remaining = 7200 - used
            if remaining < 300:
                break
            item = evidence[ref]
            rendered = (
                f"证据 {ref}｜PDF物理页 {item['physical_page']}｜"
                f"SHA256 {item['sha256']}\n{item['text']}"
            )
            rendered = rendered[:remaining]
            contexts.append({"label": ref, "text": rendered})
            used += len(rendered)
        tasks.append(
            {
                "question_id": question_id,
                "question": question,
                "retrieved_context": contexts,
                "context_characters": used,
            }
        )
    return tasks


def answer(condition: str, text_path: Path, minimal_path: Path | None, output: Path) -> int:
    if condition == "V0":
        tasks = raw_answer_tasks(source_chunks(text_path))
        persisted_chars = len(text_path.read_text(encoding="utf-8"))
    else:
        if minimal_path is None:
            raise TechnicalFailure("external_replication", "minimal artifact is required")
        minimal = json.loads(minimal_path.read_text(encoding="utf-8"))
        if minimal["source_text_sha256"] != TEXT_SHA256:
            raise TechnicalFailure("external_replication", "minimal source identity mismatch")
        tasks = minimal_answer_tasks(minimal)
        persisted_chars = len(minimal_path.read_text(encoding="utf-8"))
    instructions = [
        "Answer every question only from its retrieved_context",
        "State missing evidence instead of guessing",
        "Preserve accounting scope, time scope, limitations, and unresolved tensions",
        "Do not label different-scope statements as contradictions without evidence",
        "Use concise Simplified Chinese",
        "Return exactly one answer for Q1 through Q6",
    ]
    if condition == "V2R":
        instructions.append(
            "For each question, first infer temporary supports, limits, conflicts, and composes relations among retrieved assertions and evidence; use them in the answer but do not invent or persist new facts"
        )
    request = {
        "task": "closed_source_document_question_answering",
        "anonymous_condition": condition,
        "instructions": instructions,
        "tasks": tasks,
        "policy": {"paid_remote_calls_allowed": True, "max_remote_calls": 1},
    }
    transport, model = remote_transport(RESPONSE_SCHEMA)
    response = transport.invoke(request)
    jsonschema.Draft202012Validator(RESPONSE_SCHEMA).validate(response)
    if {item["question_id"] for item in response["answers"]} != {
        question_id for question_id, _ in QUESTIONS
    }:
        raise TechnicalFailure("external_replication", "answer IDs invalid")
    result = {
        "condition": condition,
        "model": model,
        "calls_made": transport.calls_made,
        "persisted_characters": persisted_chars,
        "context_sha256": hashlib.sha256(
            json.dumps(tasks, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "context_characters": {
            item["question_id"]: item["context_characters"] for item in tasks
        },
        "retrieved_labels": {
            item["question_id"]: [entry["label"] for entry in item["retrieved_context"]]
            for item in tasks
        },
        "answers": response["answers"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"EXTERNAL_REPLICATION_{condition}_OK")
    print(f"OUTPUT {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--text", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("answer")
    run.add_argument("--condition", choices=("V0", "V2", "V2R"), required=True)
    run.add_argument("--text", type=Path, required=True)
    run.add_argument("--minimal", type=Path)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        return build_minimal(args.text, args.output)
    return answer(args.condition, args.text, args.minimal, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
