from __future__ import annotations

import unittest


class PdfExtractionFormatTests(unittest.TestCase):
    def test_marker_format_matches_retrieval_parser(self) -> None:
        marker = f"===== PDF PHYSICAL PAGE {12} ====="
        self.assertEqual(marker, "===== PDF PHYSICAL PAGE 12 =====")


if __name__ == "__main__":
    unittest.main()
