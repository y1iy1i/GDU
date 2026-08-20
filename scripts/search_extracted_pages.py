from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("terms", nargs="+")
    parser.add_argument("--context", type=int, default=120)
    args = parser.parse_args()

    value = args.text.read_text(encoding="utf-8")
    marker = re.compile(r"===== PDF PHYSICAL PAGE (\d+) =====")
    matches = list(marker.finditer(value))
    for index, page_match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        page = value[page_match.end():end]
        found = []
        for term in args.terms:
            for match in re.finditer(re.escape(term), page, flags=re.IGNORECASE):
                start = max(0, match.start() - args.context)
                stop = min(len(page), match.end() + args.context)
                found.append((term, " ".join(page[start:stop].split())))
        if found:
            print(f"\n===== PAGE {page_match.group(1)} =====")
            seen = set()
            for term, excerpt in found:
                key = (term, excerpt)
                if key in seen:
                    continue
                seen.add(key)
                print(f"[{term}] {excerpt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
