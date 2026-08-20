from __future__ import annotations

import copy
import unittest

from gdu.builder_v0.types import TechnicalFailure
from scripts.run_remote_cp6_experiment import cp6_guidance, verify_cp6_gate


def valid_gate() -> dict[str, object]:
    required = copy.deepcopy(cp6_guidance()["required_stop_gate"])
    required.pop("summary_requirement")
    required["summary"] = "当前仅为第二节局部原型，不能冻结为完整文档GDU。"
    return required


class RemoteCp6StopGateTests(unittest.TestCase):
    def test_incomplete_document_is_correctly_refused(self) -> None:
        verify_cp6_gate(valid_gate())

    def test_local_success_cannot_pass_full_coverage(self) -> None:
        gate = valid_gate()
        gate["coverage"] = "passed"
        with self.assertRaisesRegex(TechnicalFailure, "coverage"):
            verify_cp6_gate(gate)

    def test_missing_cross_carrier_gap_is_rejected(self) -> None:
        gate = valid_gate()
        gate["gaps"] = [
            item for item in gate["gaps"] if item["check_kind"] != "cross_carrier"
        ]
        with self.assertRaisesRegex(TechnicalFailure, "three blocking gaps"):
            verify_cp6_gate(gate)

    def test_summary_must_explicitly_refuse_freeze(self) -> None:
        gate = valid_gate()
        gate["summary"] = "局部实验完成。"
        with self.assertRaisesRegex(TechnicalFailure, "refuse full freeze"):
            verify_cp6_gate(gate)


if __name__ == "__main__":
    unittest.main()
