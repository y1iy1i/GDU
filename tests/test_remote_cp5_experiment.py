from __future__ import annotations

import copy
import unittest

from gdu.builder_v0.types import TechnicalFailure
from scripts.run_remote_cp5_experiment import cp5_guidance, verify_cp5_semantics


def valid_plan() -> dict[str, dict[str, object]]:
    required = copy.deepcopy(cp5_guidance()["required_plan"])
    summaries = {
        "purpose": "帮助读者理解第二节局部样本中的利润口径、构成和改善原因。",
        "core_meaning": "扣非口径区分利润构成，经营改善和投资公允价值变化并行成立，但不能排序。",
        "content_selection": "选择归母净利润、扣非净利润、非经常性损益和原文改善原因。",
        "organization": "先说明利润口径，再说明两个并行解释，最后保留不确定性边界。",
        "constraints": "仅覆盖第二节局部样本，不代表整份年报，不能对各因素贡献排序。",
    }
    for name, section in required.items():
        section.pop("summary_requirement")
        section["summary"] = summaries[name]
    return required


class RemoteCp5SemanticAcceptanceTests(unittest.TestCase):
    def test_preregistered_local_plan_passes(self) -> None:
        verify_cp5_semantics(valid_plan())

    def test_core_summary_can_compress_detail_preserved_by_refs(self) -> None:
        plan = valid_plan()
        plan["core_meaning"]["summary"] = (
            "同时保留利润口径差异、经营改善、投资公允价值影响和不能排序的边界。"
        )
        verify_cp5_semantics(plan)

    def test_constraints_must_disclaim_whole_document_scope(self) -> None:
        plan = valid_plan()
        plan["constraints"]["summary"] = "不能对各因素贡献排序。"
        with self.assertRaisesRegex(TechnicalFailure, "scope and uncertainty"):
            verify_cp5_semantics(plan)

    def test_plan_cannot_add_an_unknown_reference(self) -> None:
        plan = valid_plan()
        plan["purpose"]["assertion_refs"].append("A-999")
        with self.assertRaisesRegex(TechnicalFailure, "unknown"):
            verify_cp5_semantics(plan)

    def test_plan_cannot_introduce_unregistered_numbers(self) -> None:
        plan = valid_plan()
        plan["core_meaning"]["summary"] += " 假设贡献率为80%。"
        with self.assertRaisesRegex(TechnicalFailure, "unregistered number"):
            verify_cp5_semantics(plan)


if __name__ == "__main__":
    unittest.main()
