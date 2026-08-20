from copy import deepcopy

from gdu.logic_v01 import (
    belnap_status,
    compile_structured_arguments,
    grounded_labels,
    recompute_after_invalidation,
    validate_aif_interface,
)


def evidence(node_id):
    return {
        "id": node_id,
        "kind": "evidence",
        "provenance": {"source_locator": "p156", "source_hash": "abc"},
    }


def claim(node_id, atom, polarity="positive", *, asserted=True, scope="consolidated"):
    return {
        "id": node_id,
        "kind": "claim",
        "atom": atom,
        "polarity": polarity,
        "asserted": asserted,
        "active": True,
        "context": {"company_scope": scope, "period": 2025},
        "provenance": {"quoted_from": ["E1"]} if asserted else {"generated_by": "I1"},
    }


def base_graph():
    return {
        "information_nodes": [
            evidence("E1"),
            claim("C-SIGN", "inventory_row_is_negative"),
            claim("C-RULE", "negative_means_inventory_increase"),
            claim("C-INCREASE", "inventory_increased", asserted=False),
        ],
        "scheme_nodes": [
            {
                "id": "I1",
                "kind": "inference",
                "premises": ["C-SIGN", "C-RULE"],
                "conclusion": "C-INCREASE",
                "rule_kind": "strict",
                "rule_id": "signed-decrease-increase",
            }
        ],
    }


def test_aif_multi_premise_compiles_to_one_structured_argument():
    graph = base_graph()
    assert validate_aif_interface(graph) == []
    arguments, attacks = compile_structured_arguments(graph)
    derived = arguments["ARG-I-I1"]
    assert derived.conclusion == "C-INCREASE"
    assert derived.ordinary_premises == {"C-SIGN", "C-RULE"}
    assert derived.rule_kind == "strict"
    assert attacks == set()
    assert grounded_labels(arguments, attacks)["ARG-I-I1"] == "accepted"


def test_belnap_both_is_separate_from_grounded_undecided():
    graph = base_graph()
    graph["information_nodes"].append(
        claim("C-NOT-INCREASE", "inventory_increased", polarity="negative")
    )
    graph["scheme_nodes"].extend(
        [
            {
                "id": "CA1", "kind": "conflict", "attack_kind": "rebut",
                "source": "C-NOT-INCREASE", "target_type": "claim", "target": "C-INCREASE"
            },
            {
                "id": "CA2", "kind": "conflict", "attack_kind": "rebut",
                "source": "C-INCREASE", "target_type": "claim", "target": "C-NOT-INCREASE"
            },
        ]
    )
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)
    assert belnap_status(graph, "inventory_increased") == "BOTH"
    assert labels["ARG-I-I1"] == "undecided"
    assert labels["ARG-P-C-NOT-INCREASE"] == "undecided"


def test_undercut_rejects_target_inference_without_refuting_premises():
    graph = base_graph()
    graph["scheme_nodes"][0]["rule_kind"] = "defeasible"
    graph["information_nodes"].append(claim("C-UNDERCUT", "table_rule_not_applicable"))
    graph["scheme_nodes"].append(
        {
            "id": "CA-U", "kind": "conflict", "attack_kind": "undercut",
            "source": "C-UNDERCUT", "target_type": "inference", "target": "I1"
        }
    )
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)
    assert labels["ARG-P-C-UNDERCUT"] == "accepted"
    assert labels["ARG-I-I1"] == "rejected"
    assert labels["ARG-P-C-SIGN"] == "accepted"
    assert labels["ARG-P-C-RULE"] == "accepted"


def test_strict_inference_cannot_be_undercut():
    graph = base_graph()
    graph["information_nodes"].append(claim("C-UNDERCUT", "table_rule_not_applicable"))
    graph["scheme_nodes"].append(
        {
            "id": "CA-U", "kind": "conflict", "attack_kind": "undercut",
            "source": "C-UNDERCUT", "target_type": "inference", "target": "I1"
        }
    )
    issues = validate_aif_interface(graph)
    assert {issue.code for issue in issues} == {"strict_inference_cannot_be_undercut"}


def test_rebut_across_different_scope_is_rejected_by_interface():
    graph = base_graph()
    graph["information_nodes"].append(
        claim("C-PARENT", "inventory_increased", polarity="negative", scope="parent_company")
    )
    graph["scheme_nodes"].append(
        {
            "id": "CA-SCOPE", "kind": "conflict", "attack_kind": "rebut",
            "source": "C-PARENT", "target_type": "claim", "target": "C-INCREASE"
        }
    )
    issues = validate_aif_interface(graph)
    assert {issue.code for issue in issues} == {"rebut_scope_mismatch"}


def test_tms_invalidation_removes_unsupported_downstream_claim():
    result = recompute_after_invalidation(base_graph(), ["C-RULE"], event_id="REV-1")
    assert "I1" not in result["active_inference_ids"]
    assert "C-INCREASE" not in result["active_claim_ids"]
    invalid = next(
        node for node in result["graph"]["information_nodes"] if node["id"] == "C-RULE"
    )
    assert invalid["provenance"]["invalidated_by"] == "REV-1"


def test_tms_alternative_inference_keeps_conclusion_active():
    graph = base_graph()
    graph["information_nodes"].append(claim("C-DIRECT", "direct_inventory_confirmation"))
    graph["scheme_nodes"].append(
        {
            "id": "I2", "kind": "inference", "premises": ["C-DIRECT"],
            "conclusion": "C-INCREASE", "rule_kind": "strict", "rule_id": "direct-confirmation"
        }
    )
    result = recompute_after_invalidation(graph, ["C-RULE"], event_id="REV-2")
    assert "I1" not in result["active_inference_ids"]
    assert "I2" in result["active_inference_ids"]
    assert "C-INCREASE" in result["active_claim_ids"]


def test_validation_is_non_mutating():
    graph = base_graph()
    before = deepcopy(graph)
    validate_aif_interface(graph)
    assert graph == before


def test_all_independent_derivation_paths_are_preserved():
    graph = base_graph()
    graph["information_nodes"].extend(
        [
            claim("C-A", "source_a"),
            claim("C-B", "source_b"),
            claim("C-MID", "intermediate", asserted=False),
            claim("C-FINAL", "final", asserted=False),
        ]
    )
    graph["scheme_nodes"].extend(
        [
            {
                "id": "I-A", "kind": "inference", "premises": ["C-A"],
                "conclusion": "C-MID", "rule_kind": "defeasible", "rule_id": "from-a"
            },
            {
                "id": "I-B", "kind": "inference", "premises": ["C-B"],
                "conclusion": "C-MID", "rule_kind": "defeasible", "rule_id": "from-b"
            },
            {
                "id": "I-FINAL", "kind": "inference", "premises": ["C-MID", "C-RULE"],
                "conclusion": "C-FINAL", "rule_kind": "defeasible", "rule_id": "combine"
            },
        ]
    )
    arguments, _ = compile_structured_arguments(graph)
    mid_paths = [arg for arg in arguments.values() if arg.conclusion == "C-MID"]
    final_paths = [arg for arg in arguments.values() if arg.conclusion == "C-FINAL"]
    assert len(mid_paths) == 2
    assert len(final_paths) == 2
    assert {arg.ordinary_premises for arg in final_paths} == {
        frozenset({"C-A", "C-RULE"}),
        frozenset({"C-B", "C-RULE"}),
    }


def test_undercut_one_branch_leaves_independent_branch_accepted():
    graph = base_graph()
    graph["information_nodes"].extend(
        [
            claim("C-A", "source_a"),
            claim("C-B", "source_b"),
            claim("C-MID", "intermediate", asserted=False),
            claim("C-FINAL", "final", asserted=False),
            claim("C-U", "source_a_rule_inapplicable"),
        ]
    )
    graph["scheme_nodes"].extend(
        [
            {
                "id": "I-A", "kind": "inference", "premises": ["C-A"],
                "conclusion": "C-MID", "rule_kind": "defeasible", "rule_id": "from-a"
            },
            {
                "id": "I-B", "kind": "inference", "premises": ["C-B"],
                "conclusion": "C-MID", "rule_kind": "defeasible", "rule_id": "from-b"
            },
            {
                "id": "I-FINAL", "kind": "inference", "premises": ["C-MID"],
                "conclusion": "C-FINAL", "rule_kind": "defeasible", "rule_id": "continue"
            },
            {
                "id": "CA-A", "kind": "conflict", "attack_kind": "undercut",
                "source": "C-U", "target_type": "inference", "target": "I-A"
            },
        ]
    )
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)
    final_paths = [arg for arg in arguments.values() if arg.conclusion == "C-FINAL"]
    path_from_a = next(arg for arg in final_paths if "C-A" in arg.ordinary_premises)
    path_from_b = next(arg for arg in final_paths if "C-B" in arg.ordinary_premises)
    assert labels[path_from_a.id] == "rejected"
    assert labels[path_from_b.id] == "accepted"


def test_inference_dependency_cycle_is_rejected_but_attack_cycle_is_allowed():
    graph = base_graph()
    graph["scheme_nodes"].append(
        {
            "id": "I-CYCLE", "kind": "inference", "premises": ["C-INCREASE"],
            "conclusion": "C-SIGN", "rule_kind": "defeasible", "rule_id": "cycle"
        }
    )
    issues = validate_aif_interface(graph)
    assert "cyclic_inference_dependency" in {issue.code for issue in issues}
