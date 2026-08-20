"""Minimal semantic query planner and bounded gap expansion for GDU v0.1."""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Iterable, Mapping

from .logic_v01 import compile_structured_arguments, grounded_labels, validate_aif_interface


CONCEPT_ALIASES = {
    "net_profit": ("净利润", "利润", "亏损"),
    "operating_cash_flow": ("经营现金流", "经营活动现金流", "经营活动产生的现金流量净额"),
    "cash_change": ("全年现金", "现金增加", "现金减少", "现金变化", "现金及现金等价物"),
    "investment_activity": ("投资活动", "投资款", "投资支出", "对外投资"),
}


def parse_question(question: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", "", question)
    concepts = sorted(
        concept
        for concept, aliases in CONCEPT_ALIASES.items()
        if any(alias in compact for alias in aliases)
    )
    if any(term in compact for term in ("为什么", "为何", "原因", "导致", "怎么解释")):
        intent = "explain"
    elif any(term in compact for term in ("是否", "是不是", "能否", "对吗", "说明", "意味着")):
        intent = "verify"
    else:
        intent = "lookup"
    years = re.findall(r"20\d{2}", compact)
    scope = "parent_company" if "母公司" in compact else "consolidated" if "合并" in compact else None
    return {
        "intent": intent,
        "concepts": concepts,
        "year": int(years[0]) if years else None,
        "company_scope": scope,
    }


def _query_structure(parsed: Mapping[str, Any]) -> dict[str, Any]:
    concepts = set(parsed["concepts"])
    if {"investment_activity", "cash_change"} <= concepts:
        return {
            "name": "missing_causal_driver",
            "target_atoms": ["investment_cash_change_driver"],
            "limitation_atoms": [],
            "source_terms": ["投资活动产生的现金流量净额", "投资支付的现金", "对外投资款支出"],
        }
    if {"net_profit", "operating_cash_flow"} <= concepts:
        limitations = []
        if "cash_change" in concepts:
            limitations = [
                "cash_and_equivalents_increased",
                "operating_cash_flow_is_not_total_cash_change",
            ]
        return {
            "name": "contrast_explanation",
            "target_atoms": ["negative_profit_positive_ocf_explained"],
            "limitation_atoms": limitations,
            "source_terms": [],
        }
    if {"operating_cash_flow", "cash_change"} <= concepts:
        return {
            "name": "claim_verification",
            "target_atoms": ["cash_and_equivalents_increased"],
            "limitation_atoms": ["operating_cash_flow_is_not_total_cash_change"],
            "source_terms": [],
        }
    return {
        "name": "unresolved",
        "target_atoms": [],
        "limitation_atoms": [],
        "source_terms": [alias for concept in concepts for alias in CONCEPT_ALIASES[concept]][:6],
    }


def _text_for_claim(claim: Mapping[str, Any]) -> str:
    values = " ".join(str(item.get("label", "")) for item in claim.get("values", []))
    return " ".join(
        (str(claim.get("atom", "")), str(claim.get("statement", "")), values)
    )


def _bigrams(text: str) -> set[str]:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text.lower())
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _lexical_seeds(graph: Mapping[str, Any], question: str, *, limit: int = 3) -> list[str]:
    query_grams = _bigrams(question)
    scored = []
    for claim in graph.get("information_nodes", []):
        if claim.get("kind") != "claim" or not claim.get("active", True):
            continue
        node_grams = _bigrams(_text_for_claim(claim))
        score = len(query_grams & node_grams)
        if score:
            scored.append((-score, str(claim["id"])))
    return [claim_id for _, claim_id in sorted(scored)[:limit]]


def expand_claim_neighborhood(
    graph: Mapping[str, Any], seed_claim_ids: Iterable[str], *, max_hops: int = 2
) -> dict[str, Any]:
    """Perform bounded, edge-typed expansion over Claim dependencies."""

    claim_ids = {
        str(node["id"])
        for node in graph.get("information_nodes", [])
        if node.get("kind") == "claim"
    }
    adjacency: dict[str, list[tuple[str, str]]] = {claim_id: [] for claim_id in claim_ids}
    for scheme in graph.get("scheme_nodes", []):
        if scheme.get("kind") == "inference":
            conclusion = str(scheme["conclusion"])
            for premise in map(str, scheme.get("premises", [])):
                adjacency[premise].append((conclusion, "inference_forward"))
                adjacency[conclusion].append((premise, "inference_backward"))
        elif scheme.get("kind") == "conflict" and scheme.get("target_type") == "claim":
            source, target = str(scheme["source"]), str(scheme["target"])
            adjacency[source].append((target, "conflict"))
            adjacency[target].append((source, "conflict"))

    seeds = [str(seed) for seed in seed_claim_ids if str(seed) in claim_ids]
    distance = {seed: 0 for seed in seeds}
    reached_by = {seed: "seed" for seed in seeds}
    queue = deque(seeds)
    while queue:
        current = queue.popleft()
        if distance[current] >= max_hops:
            continue
        for neighbor, edge_kind in sorted(adjacency[current]):
            if neighbor in distance:
                continue
            distance[neighbor] = distance[current] + 1
            reached_by[neighbor] = edge_kind
            queue.append(neighbor)
    return {
        "max_hops": max_hops,
        "nodes": [
            {"claim_id": claim_id, "distance": distance[claim_id], "reached_by": reached_by[claim_id]}
            for claim_id in sorted(distance, key=lambda item: (distance[item], item))
        ],
    }


def _claim_matches_context(claim: Mapping[str, Any], *, scope: str | None, year: int | None) -> bool:
    context = claim.get("context", {})
    if scope is not None and context.get("company_scope") != scope:
        return False
    interval = context.get("valid_time", {})
    if year is not None and interval.get("type") == "interval":
        start_year = int(str(interval.get("start", "0000"))[:4])
        end_year = int(str(interval.get("end", "9999"))[:4])
        if not start_year <= year <= end_year:
            return False
    return True


def _accepted_claims_by_atom(
    graph: Mapping[str, Any], *, scope: str | None, year: int | None
) -> dict[str, list[str]]:
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)
    info = {str(node["id"]): node for node in graph.get("information_nodes", [])}
    accepted: dict[str, set[str]] = {}
    for argument in arguments.values():
        if labels[argument.id] != "accepted":
            continue
        if not _claim_matches_context(info[argument.conclusion], scope=scope, year=year):
            continue
        atom = str(info[argument.conclusion].get("atom", ""))
        accepted.setdefault(atom, set()).add(argument.conclusion)
    return {atom: sorted(claims) for atom, claims in accepted.items()}


def plan_query(graph: Mapping[str, Any], question: str) -> dict[str, Any]:
    """Map a question to accepted Claim targets or emit an explicit graph gap."""

    issues = validate_aif_interface(graph)
    if issues:
        raise ValueError([issue.to_dict() for issue in issues])
    parsed = parse_question(question)
    structure = _query_structure(parsed)
    default_context = graph.get("default_context", {})
    effective_scope = parsed["company_scope"] or default_context.get("company_scope")
    effective_year = parsed["year"] or default_context.get("year")
    accepted = _accepted_claims_by_atom(
        graph, scope=effective_scope, year=effective_year
    )
    missing_atoms = [atom for atom in structure["target_atoms"] if not accepted.get(atom)]
    target_claim_ids = [
        accepted[atom][0] for atom in structure["target_atoms"] if accepted.get(atom)
    ]
    limitation_claim_ids = [
        accepted[atom][0] for atom in structure["limitation_atoms"] if accepted.get(atom)
    ]
    missing_atoms.extend(
        atom for atom in structure["limitation_atoms"] if not accepted.get(atom)
    )
    has_gap = bool(missing_atoms or not structure["target_atoms"])
    seeds = _lexical_seeds(graph, question) if has_gap else []
    expansion = (
        expand_claim_neighborhood(graph, seeds, max_hops=2)
        if seeds
        else {"max_hops": 2, "nodes": []}
    )
    context = {
        "company_scope": effective_scope,
        "year": effective_year,
        "resolution": {
            "company_scope": "explicit" if parsed["company_scope"] else "document_default",
            "year": "explicit" if parsed["year"] else "document_default",
        },
    }
    return {
        "question": question,
        "semantic_parse": parsed,
        "query_structure": structure["name"],
        "context": context,
        "status": "gap" if has_gap else "ready",
        "target_claim_ids": target_claim_ids,
        "limitation_claim_ids": limitation_claim_ids,
        "missing_atoms": sorted(set(missing_atoms)),
        "gap_reasons": (
            ["unresolved_query_structure"]
            if not structure["target_atoms"]
            else ["no_accepted_claim_in_context"] if missing_atoms else []
        ),
        "expansion": expansion,
        "source_lookup": {
            "required": has_gap,
            "terms": structure["source_terms"],
            "mode": "bounded_fallback_only",
        },
    }


def search_source_pages(
    pages: Mapping[int, str], terms: Iterable[str], *, limit: int = 3
) -> list[dict[str, Any]]:
    """Rank source pages after a graph gap; this is not the primary retriever."""

    term_list = [term for term in terms if term]
    ranked = []
    for page, text in pages.items():
        matched = [term for term in term_list if term in text]
        if matched:
            ranked.append((-len(matched), int(page), matched))
    return [
        {"physical_page": page, "matched_terms": matched, "status": "candidate_evidence"}
        for _, page, matched in sorted(ranked)[:limit]
    ]
