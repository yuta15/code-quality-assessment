"""隔離された作業ディレクトリからインストール済みcqaを起動する。"""

import os
import shutil
import sys
from pathlib import Path

import pytest

from .support import CLI, write_source


@pytest.fixture(scope="session")
def cqa_executable() -> str:
    executable = shutil.which(
        "cqa",
        path=f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
    )
    if executable is None:
        pytest.fail(
            "cqaコマンドが未実装または未インストールです。CLIを実装・インストールして再実行してください。",
            pytrace=False,
        )
    return executable


@pytest.fixture
def cli(cqa_executable: str, tmp_path: Path) -> CLI:
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_") or key in {"PYTHONPATH", "PYTHONHOME"}:
            del env[key]
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
            "NO_COLOR": "1",
            "TERM": "dumb",
            "COLUMNS": "240",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
        }
    )
    return CLI(cqa_executable, tmp_path, env)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return write_source(tmp_path, "入力 空白/main.py", "def answer():\n    return 42\n")
