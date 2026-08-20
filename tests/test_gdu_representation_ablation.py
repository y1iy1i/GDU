from __future__ import annotations

import unittest

from scripts.run_gdu_representation_ablation import (
    chunk_with_structure,
    collapse_relation_types,
    markdown_section,
)


class RepresentationAblationTests(unittest.TestCase):
    def test_toc_does_not_advance_all_sections(self) -> None:
        text = (
            "===== PDF PHYSICAL PAGE 4 =====\n第一节 释义\n第二节 简介\n"
            "===== PDF PHYSICAL PAGE 5 =====\n第一节 释义\n内容\n"
            "===== PDF PHYSICAL PAGE 8 =====\n第二节 简介\n内容"
        )
        chunks, _ = chunk_with_structure(text)
        page_five = next(chunk.text for chunk in chunks if chunk.label.startswith("K-P5"))
        page_eight = next(chunk.text for chunk in chunks if chunk.label.startswith("K-P8"))
        self.assertIn("第一节 释义", page_five.splitlines()[0])
        self.assertIn("第二节 简介", page_eight.splitlines()[0])

    def test_markdown_section_stops_at_next_numbered_section(self) -> None:
        text = "## 4. 原子判断\nA\n## 5. 关系\nR\n"
        self.assertEqual(markdown_section(text, 4), "## 4. 原子判断\nA")

    def test_relation_types_collapse_to_four_type_vocabulary(self) -> None:
        source = (
            "| 编号 | 端点 | 关系类型 | 关系说明 | 证据 |\n"
            "| R-001 | A → B | 口径限定 | 说明 | E-1 |\n"
            "| R-002 | C ↔ D | 跨载体冲突 | 说明 | E-2 |"
        )
        output = collapse_relation_types(source)
        self.assertIn("limits（原类型：口径限定）", output)
        self.assertIn("conflicts（原类型：跨载体冲突）", output)


if __name__ == "__main__":
    unittest.main()
