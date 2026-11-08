"""cqaの公開入口と独立したソースプロジェクトを用意する。"""

import importlib
import os
from typing import TYPE_CHECKING

import pytest

from .support import PublicModel, write_source

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


@pytest.fixture(scope="session")
def api() -> ModuleType:
    try:
        return importlib.import_module("cqa")
    except ModuleNotFoundError as error:
        if error.name != "cqa":
            raise
        pytest.fail(
            "cqaパッケージが未実装または未インストールです。公開APIを実装・インストールして再実行してください。",
            pytrace=False,
        )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return write_source(tmp_path, "入力 空白/main.py", "def answer():\n    return 42\n")


@pytest.fixture(params=["normal", "empty", "partial", "unresolved"])
def analysis(
    request: pytest.FixtureRequest, api: ModuleType, tmp_path: Path
) -> PublicModel:
    root = tmp_path / "project"
    root.mkdir()
    if request.param != "empty":
        _ = write_source(root, "main.py", "class C:\n    def f(self): return self.x\n")
    if request.param == "partial":
        _ = write_source(root, "broken.py", "def broken(:\n")
    if request.param == "unresolved":
        _ = write_source(
            root, "dynamic.py", "import importlib\nimportlib.import_module(input())\n"
        )
    result = api.analyze(root)
    assert result.status == ("partial" if request.param == "partial" else "complete")
    assert (
        result.scope.file_count
        == {"empty": 0, "normal": 1, "partial": 2, "unresolved": 2}[request.param]
    )
    return result


@pytest.fixture(autouse=True)
def isolate_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ユーザーのGit設定を変更せず、APIが参照する環境だけ分離する。"""
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
