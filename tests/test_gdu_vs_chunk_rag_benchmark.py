from __future__ import annotations

import unittest

from scripts.run_gdu_vs_chunk_rag_benchmark import Chunk, chunk_pdf_text, retrieve


class BenchmarkRetrievalTests(unittest.TestCase):
    def test_pdf_page_markers_are_preserved(self) -> None:
        chunks = chunk_pdf_text(
            "===== PDF PHYSICAL PAGE 1 =====\n甲" + "乙" * 1900 +
            "\n===== PDF PHYSICAL PAGE 2 =====\n客户集中度高"
        )
        self.assertTrue(any(chunk.label.startswith("P1-") for chunk in chunks))
        self.assertTrue(any(chunk.label.startswith("P2-") for chunk in chunks))

    def test_retrieval_prefers_matching_content(self) -> None:
        chunks = [Chunk("A", "利润分配"), Chunk("B", "客户集中度高且应收集中")]
        selected = retrieve(chunks, "客户集中度如何", budget=1000)
        self.assertEqual(selected[0].label, "B")

    def test_retrieval_respects_character_budget(self) -> None:
        chunks = [Chunk(str(index), "算力" * 600) for index in range(5)]
        selected = retrieve(chunks, "算力", budget=1200)
        self.assertLessEqual(sum(len(chunk.text) for chunk in selected), 1200)


if __name__ == "__main__":
    unittest.main()
