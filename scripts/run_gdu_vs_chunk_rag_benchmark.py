from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.types import TechnicalFailure


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = (
    ("Q1", "公司2025年经营变化的核心主线是什么？两项主业是否同等成熟、同等盈利？"),
    ("Q2", "报告中的算力业务49.69%毛利率能否直接理解为总额经济口径下的盈利率？"),
    ("Q3", "经营现金流大幅增长是否足以说明经营质量已经没有问题？还要结合什么？"),
    ("Q4", "报告对客户集中度有哪些看似不一致的表述？应该如何同时理解？"),
    ("Q5", "算力业务快速增长是否意味着未来收益已获保证？请结合时间点、合同陈述和经营风险回答。"),
    ("Q6", "报告内部有哪些不能被系统静默合并的表格、勾选项或叙述冲突或口径张力？"),
)
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answers"],
    "properties": {
        "answers": {
            "type": "array",
            "minItems": 6,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question_id", "answer", "evidence_labels"],
                "properties": {
                    "question_id": {"enum": [qid for qid, _ in QUESTIONS]},
                    "answer": {"type": "string", "minLength": 1},
                    "evidence_labels": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
        }
    },
}


@dataclass(frozen=True)
class Chunk:
    label: str
    text: str


def sliding_chunks(label: str, text: str, size: int = 1800, overlap: int = 250) -> list[Chunk]:
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
    if not cleaned:
        return []
    chunks = []
    start = 0
    index = 1
    while start < len(cleaned):
        end = min(len(cleaned), start + size)
        chunks.append(Chunk(f"{label}-C{index}", cleaned[start:end]))
        if end == len(cleaned):
            break
        start = end - overlap
        index += 1
    return chunks


def chunk_pdf_text(text: str) -> list[Chunk]:
    pattern = re.compile(r"===== PDF PHYSICAL PAGE (\d+) =====")
    matches = list(pattern.finditer(text))
    chunks: list[Chunk] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.extend(sliding_chunks(f"P{match.group(1)}", text[match.end():end]))
    return chunks


def chunk_gdu(text: str) -> list[Chunk]:
    headings = list(re.finditer(r"(?m)^(#{2,4} .+)$", text))
    chunks: list[Chunk] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", match.group(1)).strip("-")
        chunks.extend(sliding_chunks(f"GDU-{title[:42]}", text[match.start():end]))
    return chunks


def terms(text: str) -> Counter[str]:
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    values: list[str] = []
    for width in (2, 3, 4):
        values.extend(chinese[i : i + width] for i in range(len(chinese) - width + 1))
    values.extend(token.lower() for token in re.findall(r"[A-Za-z]+|\d+(?:\.\d+)?%?", text))
    return Counter(values)


def retrieve(chunks: list[Chunk], query: str, budget: int = 7200) -> list[Chunk]:
    query_terms = terms(query)
    document_terms = [terms(chunk.text) for chunk in chunks]
    dfs = Counter(term for counts in document_terms for term in counts)
    scored = []
    for chunk, counts in zip(chunks, document_terms):
        score = 0.0
        for term, query_count in query_terms.items():
            if term not in counts:
                continue
            idf = math.log((len(chunks) + 1) / (dfs[term] + 1)) + 1
            score += min(counts[term], 4) * query_count * idf * len(term)
        scored.append((score, chunk.label, chunk))
    selected: list[Chunk] = []
    used = 0
    for score, _, chunk in sorted(scored, key=lambda item: (-item[0], item[1])):
        if score <= 0:
            break
        remaining = budget - used
        if remaining < 500:
            break
        text = chunk.text[:remaining]
        selected.append(Chunk(chunk.label, text))
        used += len(text)
    return selected


def request_payload(condition: str, chunks: list[Chunk]) -> dict[str, Any]:
    tasks = []
    for question_id, question in QUESTIONS:
        selected = retrieve(chunks, question)
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
    return {
        "task": "closed_source_document_question_answering",
        "anonymous_condition": condition,
        "instructions": [
            "Answer every question only from its retrieved_context",
            "State uncertainty or missing evidence instead of guessing",
            "Preserve conflicting statements, accounting scope, time scope, and risk boundaries",
            "Do not assume that audit opinion covers all management narrative",
            "Use concise Simplified Chinese",
            "Return exactly one answer for each Q1 through Q6",
        ],
        "tasks": tasks,
        "policy": {"paid_remote_calls_allowed": True, "max_remote_calls": 1},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("A", "B"), required=True)
    parser.add_argument("--paper-text", type=Path, required=True)
    parser.add_argument("--gdu-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = args.paper_text if args.condition == "A" else args.gdu_output
    text = source.read_text(encoding="utf-8")
    chunks = chunk_pdf_text(text) if args.condition == "A" else chunk_gdu(text)
    request = request_payload(args.condition, chunks)
    context_hash = hashlib.sha256(
        json.dumps(request["tasks"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if args.dry_run:
        value = {"condition": args.condition, "context_sha256": context_hash, **request}
    else:
        config_path = ROOT / "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
        config_hash = sha256_file(config_path)
        remote = load_remote_transport_config(
            config_path, ROOT / "configs/api/remote-adapter-v1.schema.json", config_hash
        )
        transport = OpenAICompatibleRemoteTransport(
            remote,
            explicit_authorization=True,
            response_contract=RESPONSE_SCHEMA,
        )
        response = transport.invoke(request)
        jsonschema.Draft202012Validator(RESPONSE_SCHEMA).validate(response)
        if {item["question_id"] for item in response["answers"]} != {qid for qid, _ in QUESTIONS}:
            raise TechnicalFailure("gdu_vs_chunk_benchmark", "answer IDs are incomplete or duplicated")
        value = {
            "condition": args.condition,
            "model": remote.model,
            "calls_made": transport.calls_made,
            "context_sha256": context_hash,
            "context_characters": {
                item["question_id"]: item["context_characters"] for item in request["tasks"]
            },
            "retrieved_labels": {
                item["question_id"]: [context["label"] for context in item["retrieved_context"]]
                for item in request["tasks"]
            },
            "answers": response["answers"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BENCHMARK_{args.condition}_OK")
    print(f"CHUNKS {len(chunks)}")
    print(f"CONTEXT_SHA256 {context_hash}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
