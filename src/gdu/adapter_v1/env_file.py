from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(
    path: Path,
    *,
    allowed_names: Iterable[str] = (),
) -> tuple[str, ...]:
    """Load selected local secrets without overriding the process environment."""

    if not path.exists():
        return ()
    allowed = set(allowed_names)
    loaded: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid env line {line_number}")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not _ENV_NAME.fullmatch(name):
            raise ValueError(f"invalid env name on line {line_number}")
        if allowed and name not in allowed:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name not in os.environ and value:
            os.environ[name] = value
            loaded.append(name)
    return tuple(loaded)
