"""API-D01〜D15/R07: トークン閾値、独立した出現、重複SLOC集合と部分解析。"""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.e2e.cli.test_duplication import (
    MINIMUM_MATCH_TOKENS,
    comparable_tokens,
    threshold_source,
)

from .support import assert_metric, write_source

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize(("tokens", "detected"), [(49, False), (50, True), (51, True)])
def test_analyze_success_duplication_threshold(
    *, api: ModuleType, tmp_path: Path, tokens: int, detected: bool
) -> None:
    """API-D01/D05: 除外トークンを数えず49/50/51境界を検証。"""
    source = threshold_source(tokens)
    assert len(comparable_tokens(source)) == tokens
    _ = write_source(tmp_path, "a.py", source)
    _ = write_source(tmp_path, "b.py", source)
    result = api.analyze(tmp_path)
    assert_metric(result.metrics, "duplication_rate", value=100 if detected else 0)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=24, duplicated_sloc=24 if detected else 0
    )


@pytest.mark.parametrize("change", ["whitespace", "indent", "comments", "nl"])
def test_analyze_success_duplication_ignores_layout(
    *, api: ModuleType, tmp_path: Path, change: str
) -> None:
    """API-D02: 空白幅・コメント・空行・NLは一致を妨げない。"""
    source = "if True:\n" + "".join(f"    v_{i} = ({i})\n" for i in range(12))
    changed = source
    if change == "whitespace":
        changed = source.replace(" = ", "  =  ")
    elif change == "indent":
        changed = source.replace("    ", "        ")
    elif change == "comments":
        changed = source.replace("\n", " # comment\n\n")
    else:
        changed = source.replace("(5)", "(\n5\n    )")
    assert comparable_tokens(source) == comparable_tokens(changed)
    _ = write_source(tmp_path, "a.py", source)
    _ = write_source(tmp_path, "b.py", changed)
    result = api.analyze(tmp_path)
    assert_metric(result.metrics, "duplication_rate", value=100)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("v_5", "other"),
        ("= 5", "= 0x5"),
        ("'hello'", '"hello"'),
        ("+", "-"),
        ("[", "("),
    ],
)
def test_analyze_success_duplication_lexical_differences(
    *, api: ModuleType, tmp_path: Path, original: str, replacement: str
) -> None:
    """API-D03: 識別子・リテラル・演算子・区切りを正規化しない。"""
    source = threshold_source(50)
    if original == "'hello'":
        source = source.replace("= 5", "= 'hello'")
    elif original == "+":
        source = source.replace("= 5", "= +5")
    elif original == "[":
        source = source.replace("= 5", "= [5]")
    changed = source.replace(original, replacement, 1)
    if original == "[":
        changed = changed.replace("]", ")", 1)
    _ = write_source(tmp_path, "a.py", source)
    _ = write_source(tmp_path, "b.py", changed)
    result = api.analyze(tmp_path)
    assert_metric(result.metrics, "duplication_rate", value=0)


@pytest.mark.parametrize("change", ["newline", "block"])
def test_analyze_success_duplication_preserves_structure(
    *, api: ModuleType, tmp_path: Path, change: str
) -> None:
    """API-D04: 論理行終端・ブロック構造は比較対象に含める。"""
    source = threshold_source(50)
    if change == "newline":
        changed = source.replace("v_5 = 5\nv_6 = 6", "v_5 = 5; v_6 = 6")
    else:
        source = "if True:\n" + "".join(
            "    " + line + "\n" for line in source.splitlines()
        )
        changed = (
            source.replace("    v_6", "v_6")
            .replace("    v_7", "v_7")
            .replace("    v_8", "v_8")
            .replace("    v_9", "v_9")
            .replace("    v_10", "v_10")
            .replace("    tail", "tail")
        )
    _ = write_source(tmp_path, "a.py", source)
    _ = write_source(tmp_path, "b.py", changed)
    assert_metric(api.analyze(tmp_path).metrics, "duplication_rate", value=0)


@pytest.mark.parametrize(
    "locations", ["single", "overlap", "same_file", "two_files", "three_files"]
)
def test_analyze_success_duplication_independence(
    *, api: ModuleType, tmp_path: Path, locations: str
) -> None:
    """API-D06〜D08/D12〜D13: 独立2箇所以上、各行を一度計数。"""
    block = threshold_source(50)
    if locations == "single":
        _ = write_source(tmp_path, "a.py", block)
    elif locations == "overlap":
        _ = write_source(tmp_path, "a.py", "x = 1\n" * 20)
    elif locations == "same_file":
        _ = write_source(tmp_path, "a.py", block + block)
    else:
        for name in ("a.py", "b.py", "c.py")[: 3 if locations == "three_files" else 2]:
            _ = write_source(tmp_path, name, block)
    result = api.analyze(tmp_path)
    expected = 0 if locations in {"single", "overlap"} else 100
    assert_metric(result.metrics, "duplication_rate", value=expected)
    for file in result.details.files:
        assert_metric(file.metrics, "duplication_rate", value=expected)
        details = file.metrics["duplication_rate"].details
        assert details.duplicated_sloc == (0 if expected == 0 else details.sloc)


def test_analyze_success_duplication_weighted_scope(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-D11: SLOC50/150・重複各10からScope率10%を再計算。"""
    block = "".join(f"common_{i} = {i} + 1\n" for i in range(10))
    for name, count in (("a", 40), ("b", 140)):
        filler = "".join(f"{name}_{i} = {1000 + i}\n" for i in range(count))
        _ = write_source(tmp_path, f"{name}.py", block + filler)
    result = api.analyze(tmp_path)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=200, duplicated_sloc=20
    )
    assert_metric(result.metrics, "duplication_rate", value=10)
    for file in result.details.files:
        sloc = 50 if Path(file.path).name == "a.py" else 150
        assert file.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
            sloc=sloc, duplicated_sloc=10
        )
        assert_metric(file.metrics, "duplication_rate", value=10 / sloc * 100)


@pytest.mark.parametrize("failure", [False, True])
def test_analyze_success_or_failure_duplication_partner(
    *, api: ModuleType, tmp_path: Path, failure: bool
) -> None:
    """API-D14: 除外・解析失敗の相手は重複の検出対象から外す。"""
    block = threshold_source(50)
    _ = write_source(tmp_path, "a.py", block)
    _ = write_source(tmp_path, "b.py", block + ("def broken(:\n" if failure else ""))
    result = api.analyze(tmp_path, exclude=() if failure else ("b.py",))
    assert result.status == ("partial" if failure else "complete")
    assert_metric(result.metrics, "duplication_rate", value=0)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=12, duplicated_sloc=0
    )


def test_analyze_failure_duplication_zero_successful_sloc(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-D15: 成功分SLOC=0でもpartialを維持し率をnullとする。"""
    _ = write_source(tmp_path, "empty.py", "")
    _ = write_source(tmp_path, "broken.py", "def broken(:\n")
    result = api.analyze(tmp_path)
    assert result.status == "partial"
    assert_metric(result.metrics, "duplication_rate", value=None)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=0, duplicated_sloc=0
    )


def test_analyze_success_duplication_partial_lines_and_comments(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-D08〜D10: 部分一致行を数え、空行・コメントは数えない。"""
    block = "".join(
        f"common_{i} = 'text_{i}' + 'suffix'\n\n# ignored\n" for i in range(10)
    )
    _ = write_source(tmp_path, "a.py", "prefix_a = 1; " + block + "suffix_a = 1\n")
    _ = write_source(tmp_path, "b.py", "prefix_b = 2; " + block + "suffix_b = 2\n")
    result = api.analyze(tmp_path)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=22, duplicated_sloc=20
    )
    assert_metric(result.metrics, "duplication_rate", value=20 / 22 * 100)


@pytest.mark.parametrize("same_docstring", [False, True])
def test_analyze_success_docstring_tokens(
    *, api: ModuleType, tmp_path: Path, same_docstring: bool
) -> None:
    """API-D10: docstringの字句もトークン一致の判定に使用。"""
    source = 'def f():\n    "doc first"\n' + "".join(
        f"    v_{i} = {i}\n" for i in range(10)
    )
    assert len(comparable_tokens(source)) == MINIMUM_MATCH_TOKENS
    changed = (
        source if same_docstring else source.replace('"doc first"', '"doc second"')
    )
    _ = write_source(tmp_path, "a.py", source)
    _ = write_source(tmp_path, "b.py", changed)
    result = api.analyze(tmp_path)
    assert_metric(
        result.metrics, "duplication_rate", value=100 if same_docstring else 0
    )


def test_analyze_success_overlapping_ranges_count_once(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-D08/R07: 独立の相手がある重複範囲が重なる行を一度だけ計数する。"""
    lines = [f"unique_{index} = {index}\n" for index in range(30)]
    _ = write_source(tmp_path, "a.py", "".join(lines))
    _ = write_source(tmp_path, "b.py", "".join(lines[:20]))
    _ = write_source(tmp_path, "c.py", "".join(lines[10:]))
    result = api.analyze(tmp_path)
    assert result.metrics["duplication_rate"].details == api.DuplicationMetricDetails(
        sloc=70, duplicated_sloc=70
    )
    assert_metric(result.metrics, "duplication_rate", value=100)
    for file in result.details.files:
        details = file.metrics["duplication_rate"].details
        assert details.duplicated_sloc == details.sloc
