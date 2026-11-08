"""CLI-P01〜P10、C01〜C11: 保存結果の入力、計算、互換性、状態。"""

import copy
from typing import TYPE_CHECKING

import pytest

from .support import (
    CLI,
    SCOPE_FIELDS,
    Document,
    assert_analysis,
    assert_input_error,
    deny_access,
    save_json,
    write_source,
)

if TYPE_CHECKING:
    from pathlib import Path


def compare_saved(
    cli: CLI, before: Document, after: Document, *, partial: bool = False
) -> Document:
    before_path = save_json(cli.cwd / "before.json", before)
    after_path = save_json(cli.cwd / "after.json", after)
    return cli.json(
        "compare",
        "--before-result",
        before_path,
        "--after-result",
        after_path,
        partial=partial,
    )


@pytest.mark.parametrize(
    ("before_dir", "after_dir"),
    [(False, False), (True, True), (False, True), (True, False)],
)
def test_compare_success_source_combinations(
    *, cli: CLI, tmp_path: Path, before_dir: bool, after_dir: bool
) -> None:
    """CLI-P01/P10: 配置・識別子・定義数の違いに依存せずScopeを比較する。"""
    before = write_source(tmp_path, "before/old.py", "def old(): pass\n")
    after = write_source(
        tmp_path,
        "after/nested/new.py",
        "class New: pass\ndef new(): pass\ndef extra(): pass\n",
    )
    result = cli.json(
        "compare",
        before.parent if before_dir else before,
        after.parent.parent if after_dir else after,
    )
    assert result["type"] == "comparison"
    assert_analysis(result["before"], 1)
    assert_analysis(result["after"], 1)
    assert result["differences"]["sloc"]["total"] == {
        "before": 1,
        "after": 3,
        "difference": 2,
        "change_rate": 200,
    }
    assert result["differences"]["function_count"]["total"]["difference"] == 1


@pytest.mark.parametrize("saved_side", ["before", "after", "both"])
@pytest.mark.parametrize("change", ["delete", "rewrite"])
def test_compare_success_saved_values(
    *, cli: CLI, source: Path, saved_side: str, change: str
) -> None:
    """CLI-P02〜P04/P06: 拡張子を問わず結果を読み、元ソースを再解析しない。"""
    saved = cli.analyze(source)
    result_path = save_json(cli.cwd / "saved.data", saved)
    if change == "delete":
        source.unlink()
    else:
        _ = source.write_text("class Different: pass\n", encoding="utf-8")
    fresh = write_source(cli.cwd, "fresh.py", "x = 1\n")
    if saved_side == "both":
        result = cli.json(
            "compare", "--before-result", result_path, "--after-result", result_path
        )
        assert result["before"] == result["after"] == saved
    else:
        result = cli.json("compare", fresh, f"--{saved_side}-result", result_path)
        other = "after" if saved_side == "before" else "before"
        assert result[saved_side] == saved
        assert result[other]["metrics"]["sloc"]["total"] == 1


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("source",),
        ("--before-result", "saved"),
        ("--after-result", "saved"),
        ("source", "source", "--before-result", "saved"),
        ("source", "source", "--after-result", "saved"),
        ("source", "--before-result", "saved", "--after-result", "saved"),
    ],
)
def test_compare_failure_input_combination(
    *, cli: CLI, source: Path, args: tuple[str, ...]
) -> None:
    """CLI-P05: 各側の不足と同じ側への入力重複を拒否する。"""
    saved = save_json(cli.cwd / "saved.json", cli.analyze(source))
    mapping = {"source": source, "saved": saved}
    assert_input_error(cli.run("compare", *(mapping.get(arg, arg) for arg in args)))


def test_compare_failure_json_as_source(*, cli: CLI, source: Path) -> None:
    """CLI-P06: 位置引数の.jsonはソースとして扱い、結果入力と推測しない。"""
    saved = save_json(cli.cwd / "saved.json", cli.analyze(source))
    process = cli.run("compare", saved, source)
    assert_input_error(process)
    assert "UNSUPPORTED_FILE_TYPE" in process.stderr


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("denied", [False, True])
def test_compare_failure_source_target(
    *, cli: CLI, source: Path, side: str, denied: bool
) -> None:
    """CLI-P07: Before/After双方の対象エラーをstderrに出す。"""
    invalid = cli.cwd / "invalid.py"
    original = None
    if denied:
        _ = invalid.write_text("x = 1\n", encoding="utf-8")
        original = deny_access(invalid, "read")
    args = (invalid, source) if side == "before" else (source, invalid)
    try:
        process = cli.run("compare", *args)
        assert_input_error(process)
        assert (
            "TARGET_ACCESS_DENIED" if denied else "TARGET_NOT_FOUND"
        ) in process.stderr
        assert invalid.name in process.stderr
    finally:
        if original is not None:
            invalid.chmod(original)


def corrupt(document: Document, kind: str) -> None:  # noqa: C901 -- 公開スキーマの破損箇所を列挙。
    """公開スキーマの確定済み読み込みエラーだけを作る。"""
    if kind == "schema":
        document["schema_version"] = "unsupported-future-schema"
        return
    if kind == "scope":
        del document["scope"]
    elif kind == "files_type":
        document["details"]["files"] = {}
    elif kind == "aggregate":
        del document["metrics"]["sloc"]["total"]
    elif kind == "aggregate_type":
        document["metrics"]["sloc"]["total"] = "two"
    elif kind == "duplicate_id":
        document["details"]["files"].append(
            copy.deepcopy(document["details"]["files"][0])
        )
    elif kind in {"file_id", "parent_id"}:
        document["details"]["functions"][0][kind] = "nonexistent-id"
    elif kind == "cycle_id":
        document["metrics"]["dependency_cycles"] = {
            "value": 1,
            "details": {
                "groups": [[document["details"]["files"][0]["id"], "nonexistent-id"]]
            },
        }
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "denied",
        "invalid_json",
        "comparison",
        "scope",
        "files_type",
        "aggregate",
        "aggregate_type",
        "duplicate_id",
        "file_id",
        "parent_id",
        "cycle_id",
        "schema",
        "console",
        "markdown",
    ],
)
def test_compare_failure_saved_input(
    *, cli: CLI, source: Path, side: str, kind: str
) -> None:
    """CLI-P08〜P09: 壊れた保存入力を比較可能0件の成功結果にしない。"""
    document = cli.analyze(source)
    valid = save_json(cli.cwd / "valid.json", document)
    invalid = cli.cwd / "invalid.json"
    original = None
    if kind in {"console", "markdown"}:
        report = cli.run("analyze", source, "--format", kind)
        assert report.returncode == 0, report.stderr
        _ = invalid.write_text(report.stdout, encoding="utf-8")
    elif kind == "comparison":
        _ = save_json(invalid, cli.json("compare", source, source))
    elif kind == "invalid_json":
        _ = invalid.write_text("{broken", encoding="utf-8")
    elif kind != "missing":
        if kind != "denied":
            corrupt(document, kind)
        _ = save_json(invalid, document)
        if kind == "denied":
            original = deny_access(invalid, "read")
    inputs = {"before": valid, "after": valid, side: invalid}
    try:
        assert_input_error(
            cli.run(
                "compare",
                "--before-result",
                inputs["before"],
                "--after-result",
                inputs["after"],
                "--format",
                "json",
            )
        )
    finally:
        if original is not None:
            invalid.chmod(original)


def test_compare_success_all_scope_items(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-C01: 全Scope集計項目を独立して比較し、保持精度で計算する。"""
    path = write_source(
        tmp_path, "full.py", "class A:\n    def f(self):\n        return self.x\n"
    )
    before = cli.analyze(path)
    after = copy.deepcopy(before)
    for index, (metric, fields) in enumerate(SCOPE_FIELDS.items(), start=1):
        for field in fields:
            before["metrics"][metric][field] = index
            after["metrics"][metric][field] = index + 1
    result = compare_saved(cli, before, after)
    for metric, fields in SCOPE_FIELDS.items():
        assert set(result["differences"][metric]) == set(fields)
        for field in fields:
            a, b = before["metrics"][metric][field], after["metrics"][metric][field]
            assert result["differences"][metric][field] == pytest.approx(
                {
                    "before": a,
                    "after": b,
                    "difference": b - a,
                    "change_rate": (b - a) / a * 100,
                }
            )


@pytest.mark.parametrize(
    ("before_value", "after_value", "difference", "rate"),
    [
        (10, 5, -5, -50),
        (5, 10, 5, 100),
        (5, 5, 0, 0),
        (0, 5, 5, None),
        (5, 0, -5, -100),
        (0, 0, 0, None),
        (5, 15, 10, 200),
    ],
)
def test_compare_success_arithmetic(
    *,
    cli: CLI,
    before_value: int,
    after_value: int,
    difference: int,
    rate: int | None,
) -> None:
    """CLI-C02: 増減・同値・0分母・100%超の変化率を独立期待値で検証。"""
    before = cli.analyze(write_source(cli.cwd, "source.py"))
    after = copy.deepcopy(before)
    before["metrics"]["sloc"]["total"] = before_value
    after["metrics"]["sloc"]["total"] = after_value
    result = compare_saved(cli, before, after)
    assert result["differences"]["sloc"]["total"] == {
        "before": before_value,
        "after": after_value,
        "difference": difference,
        "change_rate": rate,
    }
    if rate is None:
        assert any(
            item["metric"] == "sloc" and item["reason"]
            for item in result["incompatible_metrics"]
        )


@pytest.mark.parametrize(
    ("before_value", "after_value"), [(None, 5), (5, None), (None, None)]
)
def test_compare_success_unavailable(
    *, cli: CLI, source: Path, before_value: int | None, after_value: int | None
) -> None:
    """CLI-C02: nullを0に置換せず計測不能の理由を残す。"""
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    for document, value in ((before, before_value), (after, after_value)):
        document["metrics"]["function_length"]["average"] = value
        if value is None:
            document["metrics"]["function_length"]["unavailable_reason"] = (
                "NO_FUNCTIONS"
            )
    result = compare_saved(cli, before, after)
    item = result["differences"].get("function_length", {}).get("average")
    if item is not None:
        assert item["difference"] is None
        assert item["change_rate"] is None
    assert any(
        item["metric"] == "function_length" and item["reason"]
        for item in result["incompatible_metrics"]
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_compare_success_percentage_precision(
    *, cli: CLI, source: Path, reverse: bool
) -> None:
    """CLI-C02: 割合差分はpt、入れ替え後の変化率は新しいBeforeを基準。"""
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    before["metrics"]["duplication_rate"]["value"] = 15
    after["metrics"]["duplication_rate"]["value"] = 10
    if reverse:
        before, after = after, before
    result = compare_saved(cli, before, after)
    item = result["differences"]["duplication_rate"]["value"]
    assert item["difference"] == (5 if reverse else -5)
    assert item["change_rate"] == pytest.approx(50 if reverse else -100 / 3)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_metric",
        "tool_version",
        "definition",
        "setting",
        "missing_model",
        "unknown_setting",
    ],
)
def test_compare_success_compatibility(*, cli: CLI, source: Path, kind: str) -> None:
    """CLI-C03〜C06/O19: 構造検証と指標単位の互換性判定を分離する。"""
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    model = after["metadata"]["measurement_models"]["duplication_rate"]
    if kind == "missing_metric":
        del after["metrics"]["duplication_rate"]
    elif kind == "tool_version":
        after["metadata"]["tool_version"] = "999.0.0"
    elif kind == "definition":
        model["definition_version"] = "unknown-definition"
    elif kind == "setting":
        model["settings"]["minimum_match_tokens"] = 51
    elif kind == "missing_model":
        del after["metadata"]["measurement_models"]["duplication_rate"]
    else:
        model["settings"]["unknown-setting"] = True
    result = compare_saved(cli, before, after)
    assert result["differences"]["sloc"]["total"]["difference"] == 0
    if kind == "tool_version":
        assert result["differences"]["duplication_rate"]["value"]["difference"] == 0
    else:
        assert (
            "duplication_rate" not in result["differences"]
            or not result["differences"]["duplication_rate"]
        )
        assert any(
            item["metric"] == "duplication_rate" and item["reason"]
            for item in result["incompatible_metrics"]
        )


@pytest.mark.parametrize(
    ("before_partial", "after_partial"),
    [(False, False), (False, True), (True, False), (True, True)],
)
@pytest.mark.parametrize("saved", [False, True])
def test_compare_success_or_failure_status(
    *, cli: CLI, tmp_path: Path, before_partial: bool, after_partial: bool, saved: bool
) -> None:
    """CLI-C08: ソース・保存入力の全状態組で成功分と両側エラーを保持。"""
    roots = [tmp_path / side for side in ("before", "after")]
    for root, partial in zip(roots, (before_partial, after_partial), strict=True):
        _ = write_source(root, "good.py")
        if partial:
            _ = write_source(root, "broken.py", "def broken(:\n")
    partial = before_partial or after_partial
    if saved:
        result = compare_saved(
            cli,
            cli.analyze(roots[0], partial=before_partial),
            cli.analyze(roots[1], partial=after_partial),
            partial=partial,
        )
    else:
        result = cli.json("compare", *roots, partial=partial)
    assert result["differences"]["sloc"]["total"]["difference"] == 0
    for side, expected in (("before", before_partial), ("after", after_partial)):
        assert bool(result[side]["errors"]) == expected
        assert result[side]["status"] == ("partial" if expected else "complete")


@pytest.mark.parametrize("partial", [False, True])
def test_compare_success_or_failure_no_comparable(
    *, cli: CLI, source: Path, partial: bool
) -> None:
    """CLI-C07/C09: 全指標が未知定義でも状態は双方の解析状態に従う。"""
    before = cli.analyze(source)
    if partial:
        _ = write_source(source.parent, "broken.py", "def broken(:\n")
        before = cli.analyze(source.parent, partial=True)
    after = copy.deepcopy(before)
    for model in after["metadata"]["measurement_models"].values():
        model["definition_version"] = "unknown-definition"
    result = compare_saved(cli, before, after, partial=partial)
    assert not result["differences"] or not any(result["differences"].values())
    assert result["incompatible_metrics"]
    assert all(item["reason"] for item in result["incompatible_metrics"])
    assert result["before"] == before
    assert result["after"] == after


@pytest.mark.parametrize("nonempty", [False, True])
def test_compare_success_empty_scope(
    *, cli: CLI, tmp_path: Path, nonempty: bool
) -> None:
    """CLI-C11: 対象0件同士と空対非空で0/nullの比較規則を適用。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    after = write_source(tmp_path, "nonempty.py") if nonempty else empty
    result = cli.json("compare", empty, after)
    assert result["before"]["scope"]["file_count"] == 0
    assert result["after"]["scope"]["file_count"] == int(nonempty)
    assert result["differences"]["sloc"]["total"]["difference"] == int(nonempty)


def test_compare_success_retains_unresolved_cbo(*, cli: CLI) -> None:
    """CLI-C10: CBO確定値3→2と未解決5件を保持し、completeのまま比較。"""
    source = write_source(cli.cwd, "classes.py", "class C:\n    def f(self): pass\n")
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    target = after["details"]["classes"][0]["id"]
    before["metrics"]["cbo"].update(average=3, maximum=3)
    after["metrics"]["cbo"].update(average=2, maximum=2)
    after["unresolved"] = [
        {"metric": "cbo", "target": target, "reason": f"Unresolved reference {index}"}
        for index in range(5)
    ]
    result = compare_saved(cli, before, after)
    assert result["differences"]["cbo"]["average"]["difference"] == -1
    assert result["before"]["unresolved"] == []
    assert result["after"]["unresolved"] == after["unresolved"]
