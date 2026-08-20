from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

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
    request_payload,
    sliding_chunks,
)


ROOT = Path(__file__).resolve().parents[1]
ORDINALS = "一二三四五六七八"


def split_pdf_pages(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"===== PDF PHYSICAL PAGE (\d+) =====")
    matches = list(pattern.finditer(text))
    pages = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[match.end():end].strip()))
    return pages


def chunk_with_structure(text: str) -> tuple[list[Chunk], str]:
    pages = split_pdf_pages(text)
    expected_index = 0
    current_section = "报告前置部分"
    chunks: list[Chunk] = []
    rendered: list[str] = []
    for page, page_text in pages:
        if expected_index < len(ORDINALS):
            expected = ORDINALS[expected_index]
            match = re.search(rf"(?m)^第{expected}节\s+[^\n]+", page_text)
            if match:
                current_section = match.group(0).strip()
                expected_index += 1
        prefix = f"[物理页 {page}｜{current_section}]\n"
        rendered.append(prefix + page_text)
        chunks.extend(sliding_chunks(f"K-P{page}", prefix + page_text))
    return chunks, "\n\n".join(rendered)


def markdown_section(text: str, number: int) -> str:
    match = re.search(rf"(?m)^## {number}\. .+$", text)
    if not match:
        raise TechnicalFailure("gdu_representation_ablation", f"section {number} missing")
    next_match = re.search(r"(?m)^## \d+\. .+$", text[match.end():])
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.start():end].strip()


def collapse_relation_types(relation_section: str) -> str:
    mapping = {
        "supports": ("支撑", "独立核验", "实例化风险", "信用暴露", "前瞻响应", "供应链关系", "合规背景"),
        "limits": ("限制", "口径限定", "鉴证边界", "财务约束", "信息限制", "约束", "负面推断边界"),
        "conflicts": ("冲突", "跨载体冲突"),
        "composes": ("组成", "构成", "操作化", "义务扩展", "期后融资"),
    }
    output = []
    for line in relation_section.splitlines():
        if line.startswith("| R-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= 5:
                original = cells[2]
                collapsed = next(
                    (
                        target
                        for target, names in mapping.items()
                        if any(name in original for name in names)
                    ),
                    "supports",
                )
                cells[2] = f"{collapsed}（原类型：{original}）"
                line = "| " + " | ".join(cells) + " |"
        output.append(line)
    return "\n".join(output)


def derived_representation(condition: str, paper: str, gdu: str) -> tuple[list[Chunk], str, int]:
    if condition == "V1":
        chunks, representation = chunk_with_structure(paper)
        return chunks, representation, 2
    assertions = markdown_section(gdu, 4)
    evidence = markdown_section(gdu, 7)
    if condition == "V2":
        representation = assertions + "\n\n" + evidence
        category_count = 2
    elif condition == "V3":
        relations = collapse_relation_types(markdown_section(gdu, 5))
        representation = assertions + "\n\n" + relations + "\n\n" + evidence
        category_count = 3
    else:
        raise ValueError(condition)
    chunks = []
    for index, part in enumerate(re.split(r"(?m)(?=^## )", representation)):
        chunks.extend(sliding_chunks(f"K-S{index}", part))
    return chunks, representation, category_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("V1", "V2", "V3"), required=True)
    parser.add_argument("--paper-text", type=Path, required=True)
    parser.add_argument("--gdu-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paper = args.paper_text.read_text(encoding="utf-8")
    gdu = args.gdu_output.read_text(encoding="utf-8")
    chunks, representation, category_count = derived_representation(
        args.condition, paper, gdu
    )
    request = request_payload(args.condition, chunks)
    context_hash = hashlib.sha256(
        json.dumps(request["tasks"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    common: dict[str, Any] = {
        "condition": args.condition,
        "representation_characters": len(representation),
        "retrieval_chunks": len(chunks),
        "object_categories": category_count,
        "context_sha256": context_hash,
        "context_characters": {
            item["question_id"]: item["context_characters"] for item in request["tasks"]
        },
        "retrieved_labels": {
            item["question_id"]: [context["label"] for context in item["retrieved_context"]]
            for item in request["tasks"]
        },
    }
    if args.dry_run:
        value = {**common, "request": request}
    else:
        config_path = ROOT / "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
        config_hash = sha256_file(config_path)
        remote = load_remote_transport_config(
            config_path, ROOT / "configs/api/remote-adapter-v1.schema.json", config_hash
        )
        transport = OpenAICompatibleRemoteTransport(
            remote, explicit_authorization=True, response_contract=RESPONSE_SCHEMA
        )
        response = transport.invoke(request)
        jsonschema.Draft202012Validator(RESPONSE_SCHEMA).validate(response)
        if {item["question_id"] for item in response["answers"]} != {
            f"Q{index}" for index in range(1, 7)
        }:
            raise TechnicalFailure("gdu_representation_ablation", "answer IDs invalid")
        value = {
            **common,
            "model": remote.model,
            "calls_made": transport.calls_made,
            "answers": response["answers"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ABLATION_{args.condition}_OK")
    print(f"REPRESENTATION_CHARACTERS {len(representation)}")
    print(f"CHUNKS {len(chunks)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
