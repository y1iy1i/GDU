from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from gdu.adapter_v1.env_file import load_env_file


def test_env_file_loads_only_allowed_names_without_overriding(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "DASHSCOPE_API_KEY='local-secret'\nIGNORED_VALUE=not-loaded\n",
        encoding="utf-8",
    )

    with patch.dict(os.environ, {}, clear=True):
        loaded = load_env_file(path, allowed_names={"DASHSCOPE_API_KEY"})
        assert loaded == ("DASHSCOPE_API_KEY",)
        assert os.environ["DASHSCOPE_API_KEY"] == "local-secret"
        assert "IGNORED_VALUE" not in os.environ

    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "process-secret"}, clear=True):
        loaded = load_env_file(path, allowed_names={"DASHSCOPE_API_KEY"})
        assert loaded == ()
        assert os.environ["DASHSCOPE_API_KEY"] == "process-secret"
