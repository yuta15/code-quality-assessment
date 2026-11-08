"""API-S01〜S10/X01〜X16/M04: 規模、構文ごとの複雑度、定義の所属と集計。"""

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .support import assert_metric, single, write_source

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize(
    ("source", "sloc"),
    [
        ("", 0),
        (" \n\t\n", 0),
        ("# comment\n", 0),
        ("x = 1 # comment\n", 1),
        ("x = 1; y = 2\n", 1),
        (
            (
                "# Calculation utility\n"
                "\n"
                "def add(a, b):\n"
                "    return a + b  # Return result\n"
            ),
            2,
        ),
    ],
)
def test_analyze_success_sloc(
    *, api: ModuleType, tmp_path: Path, source: str, sloc: int
) -> None:
    """API-S01〜S03: SLOCの物理行・空白・コメントの規則。"""
    result = api.analyze(write_source(tmp_path, "size.py", source))
    assert_metric(result.metrics, "sloc", total=sloc)
    assert_metric(result.details.files[0].metrics, "sloc", total=sloc)


@pytest.mark.parametrize(
    ("source", "lengths"),
    [
        ("def f(): pass\n", [1]),
        ("def f():\n    pass\n", [2]),
        ("def f():\n    ...\n", [2]),
        (
            (
                "@first\n"
                "@second(\n"
                "    1\n"
                ")\n"
                "def f(\n"
                "    value,\n"
                "):\n"
                '    "doc"\n'
                "\n"
                "    # comment\n"
                "    return value\n"
                "\n"
                "\n"
                "x = 1\n"
            ),
            [11],
        ),
        ("def outer():\n    def inner():\n        pass\n    return inner\n", [4, 2]),
    ],
)
def test_analyze_success_function_length(
    *, api: ModuleType, tmp_path: Path, source: str, lengths: list[int]
) -> None:
    """API-S04〜S06: デコレータ・空行・内側定義を含む関数長。"""
    result = api.analyze(write_source(tmp_path, "length.py", source))
    assert sorted(
        item.metrics["function_length"].value for item in result.details.functions
    ) == sorted(lengths)
    assert_metric(result.metrics, "function_count", total=len(lengths))
    assert_metric(
        result.metrics,
        "function_length",
        average=sum(lengths) / len(lengths),
        maximum=max(lengths),
    )


@pytest.mark.parametrize(
    "declaration",
    [
        "def f(): pass",
        "async def f(): pass",
        "class C:\n    def __init__(self): pass",
        "class C:\n    @staticmethod\n    def f(): pass",
        "class C:\n    @classmethod\n    def f(cls): pass",
        (
            "class C:\n"
            "    @property\n"
            "    def f(self): pass\n"
            "    @f.setter\n"
            "    def f(self, value): pass\n"
            "    @f.deleter\n"
            "    def f(self): pass"
        ),
        "def f(): pass\ndef f(): pass",
    ],
)
def test_analyze_success_function_kinds(
    *, api: ModuleType, tmp_path: Path, declaration: str
) -> None:
    """API-S07: async・特殊・各アクセサ・再定義も個別計数。"""
    result = api.analyze(write_source(tmp_path, "kinds.py", declaration + "\n"))
    expected = declaration.count("def ")
    assert_metric(result.metrics, "function_count", total=expected)
    assert len(result.details.functions) == expected
    assert all(
        item.metrics["function_length"].value >= 1 for item in result.details.functions
    )


def test_analyze_success_lambda_and_import_not_counted(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-S08: lambdaとimportは関数定義に数えない。"""
    result = api.analyze(
        write_source(
            tmp_path, "no_functions.py", "from os import getcwd\nf = lambda: 1\n"
        )
    )
    assert_metric(result.metrics, "function_count", total=0)
    assert_metric(result.metrics, "function_length", average=None, maximum=None)
    assert not result.details.functions


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("class C: pass\n", 1),
        ("class Base: pass\nclass Child(Base): pass\n", 2),
        ("@decorate\nclass C: pass\n", 1),
        ("class Outer:\n    class Inner: pass\n", 2),
        ("def f():\n    class Local: pass\n", 1),
        ("class C: pass\nclass C: pass\n", 2),
        ("from pathlib import Path\n", 0),
    ],
)
def test_analyze_success_class_kinds(
    *, api: ModuleType, tmp_path: Path, source: str, count: int
) -> None:
    """API-S09: 各class定義を計数し、importされたクラスは除く。"""
    result = api.analyze(write_source(tmp_path, "classes.py", source))
    assert_metric(result.metrics, "class_count", total=count)
    assert len(result.details.classes) == count


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("return 1", (1, 0, 0)),
        ("if a:\n    pass", (2, 1, 1)),
        ("if a:\n    pass\nelse:\n    pass", (2, 1, 2)),
        ("if a:\n    pass\nelif b:\n    pass", (3, 1, None)),
        ("for x in xs:\n    pass", (2, 1, None)),
        ("async for x in xs:\n    pass", (2, 1, None)),
        ("while a:\n    pass", (2, 1, None)),
        ("with context:\n    pass", (2, 1, None)),
        ("async with context:\n    pass", (2, 1, None)),
        ("for x in xs:\n    pass\nelse:\n    pass", (3, 1, None)),
        ("while a:\n    pass\nelse:\n    pass", (3, 1, None)),
        ("try:\n    pass\nexcept ValueError:\n    pass", (2, 1, None)),
        (
            "try:\n    pass\nexcept ValueError:\n    pass\nexcept TypeError:\n    pass",
            (3, 1, None),
        ),
        ("try:\n    pass\nexcept* ValueError:\n    pass", (2, 1, None)),
        (
            (
                "try:\n"
                "    pass\n"
                "except* ValueError:\n"
                "    pass\n"
                "except* TypeError:\n"
                "    pass"
            ),
            (3, 1, None),
        ),
        (
            (
                "try:\n"
                "    pass\n"
                "except ValueError:\n"
                "    pass\n"
                "else:\n"
                "    pass\n"
                "finally:\n"
                "    pass"
            ),
            (3, 1, None),
        ),
        ("try:\n    pass\nfinally:\n    pass", (1, 1, None)),
        ("assert a", (2, 0, None)),
        ("return a if b else c", (2, 0, None)),
        ("if a and b:\n    pass", (3, 1, None)),
        ("if a and b or c:\n    pass", (4, 1, None)),
        ("return [x for x in xs if x]", (3, 0, None)),
        ("return {x for x in xs if x}", (3, 0, None)),
        ("return {x: x for x in xs if x}", (3, 0, None)),
        ("return (x for x in xs if x)", (3, 0, None)),
        ("return [x for xs in groups for x in xs if x if a]", (5, 0, None)),
        (
            "match a:\n    case 1: pass\n    case 2: pass\n    case _: pass",
            (3, 1, None),
        ),
        ("match a:\n    case _: pass", (1, 1, None)),
        ("match a:\n    case _ if a and b: pass", (3, 1, None)),
        ("if a:\n    if b:\n        pass", (3, 2, 3)),
        ("for x in xs:\n    if x:\n        pass", (3, 2, 3)),
        (
            (
                "if a:\n"
                "    if b:\n"
                "        pass\n"
                "    elif c:\n"
                "        pass\n"
                "    else:\n"
                "        pass"
            ),
            (4, 2, None),
        ),
        ("if a:\n    pass\nfor x in xs:\n    pass", (3, 1, None)),
        ("while a:\n    with context:\n        pass", (3, 2, None)),
        ("service.run()\nhelper()", (1, 0, 0)),
    ],
)
def test_analyze_success_complexity_syntax(
    *, api: ModuleType, tmp_path: Path, body: str, expected: tuple[int, int, int | None]
) -> None:
    """API-X01〜X11/X15〜X16: 構文別CC・深度・確定Cog。"""
    cc, depth, cog = expected
    source = "async def f():\n" + textwrap.indent(body, "    ") + "\n"
    result = api.analyze(write_source(tmp_path, "complexity.py", source))
    metrics = single(result, "functions", "f").metrics
    assert_metric(metrics, "cyclomatic_complexity", value=cc)
    assert_metric(metrics, "nesting_depth", value=depth)
    if cog is not None:
        assert_metric(metrics, "cognitive_complexity", value=cog)
    assert_metric(
        result.metrics, "cyclomatic_complexity", total=cc, average=cc, maximum=cc
    )
    assert_metric(result.metrics, "nesting_depth", average=depth, maximum=depth)


@pytest.mark.parametrize(
    "wrapper", ["def outer():\n{body}", "class C:\n    def method(self):\n{nested}"]
)
def test_analyze_success_nested_function_boundary(
    *, api: ModuleType, tmp_path: Path, wrapper: str
) -> None:
    """API-X12: 内側の分岐を外側関数に加算しない。"""
    body = "    def inner():\n        if flag:\n            pass\n"
    source = wrapper.format(body=body, nested=textwrap.indent(body, "    "))
    result = api.analyze(write_source(tmp_path, "nested.py", source))
    outer_name = "method" if "class C" in source else "outer"
    assert_metric(
        single(result, "functions", outer_name).metrics,
        "cyclomatic_complexity",
        value=1,
    )
    assert_metric(
        single(result, "functions", outer_name).metrics, "nesting_depth", value=0
    )
    assert_metric(
        single(result, "functions", "inner").metrics, "cyclomatic_complexity", value=2
    )
    assert_metric(
        single(result, "functions", "inner").metrics, "nesting_depth", value=1
    )


def test_analyze_success_module_and_class_branch_boundary(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-X13: 関数外の分岐はクラス独自スコアを作らない。"""
    source = (
        "if flag:\n"
        "    pass\n"
        "class C:\n"
        "    if flag:\n"
        "        pass\n"
        "    def f(self):\n"
        "        pass\n"
    )
    result = api.analyze(write_source(tmp_path, "outside.py", source))
    assert_metric(
        single(result, "functions", "f").metrics, "cyclomatic_complexity", value=1
    )
    assert_metric(
        single(result, "classes", "C").metrics,
        "cyclomatic_complexity",
        total=1,
        average=1,
        maximum=1,
    )
    assert single(result, "classes", "C").metrics["cyclomatic_complexity"].value is None


@pytest.mark.parametrize(
    "prefix",
    [
        "def f():",
        "async def f():",
        "class C:\n    def __call__(self):",
        "class C:\n    @staticmethod\n    def f():",
        "class C:\n    @classmethod\n    def f(cls):",
    ],
)
def test_analyze_success_method_complexity(
    *, api: ModuleType, tmp_path: Path, prefix: str
) -> None:
    """API-X14: async・特殊・static/classメソッドも同じ計数。"""
    indent = "        " if prefix.startswith("class") else "    "
    source = prefix + "\n" + indent + "if flag:\n" + indent + "    pass\n"
    result = api.analyze(write_source(tmp_path, "method.py", source))
    assert_metric(result.details.functions[0].metrics, "cyclomatic_complexity", value=2)


def test_analyze_success_weighted_aggregation(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-M04/S10: ファイル平均ではなく個別定義で集計。"""
    _ = write_source(tmp_path, "one.py", "def a(): pass\n")
    _ = write_source(
        tmp_path,
        "two.py",
        (
            "class C: pass\n"
            "def b(): pass\n"
            "def c():\n"
            "    if a:\n"
            "        pass\n"
            "    if b:\n"
            "        pass\n"
            "    if c:\n"
            "        pass\n"
        ),
    )
    result = api.analyze(tmp_path)
    assert_metric(result.metrics, "sloc", total=10)
    assert_metric(result.metrics, "function_count", total=3)
    assert_metric(result.metrics, "class_count", total=1)
    assert_metric(result.metrics, "function_length", average=3, maximum=7)
    assert_metric(
        result.metrics, "cyclomatic_complexity", total=6, average=2, maximum=4
    )


@pytest.mark.parametrize(
    "body",
    [
        "async for x in xs:\n    pass\nelse:\n    pass",
        (
            "try:\n"
            "    pass\n"
            "except* ValueError:\n"
            "    pass\n"
            "else:\n"
            "    pass\n"
            "finally:\n"
            "    pass"
        ),
    ],
)
def test_analyze_success_async_sibling_clauses(
    *, api: ModuleType, tmp_path: Path, body: str
) -> None:
    """API-X03〜X04: asyncループelse・except*のelse/finallyも兄弟節として計数。"""
    source = "async def f():\n" + textwrap.indent(body, "    ") + "\n"
    result = api.analyze(write_source(tmp_path, "async_clauses.py", source))
    metrics = single(result, "functions", "f").metrics
    assert_metric(metrics, "cyclomatic_complexity", value=3)
    assert_metric(metrics, "nesting_depth", value=1)


def test_analyze_success_cognitive_aggregation(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-M02/M04: 非ゼロCog・深度・関数長を個別定義からClass/File/Scopeへ集計。"""
    _ = write_source(tmp_path, "a.py", "def a():\n    if flag:\n        return 1\n")
    _ = write_source(
        tmp_path,
        "b.py",
        (
            "class C:\n"
            "    def b(self):\n"
            "        if flag:\n"
            "            return 1\n"
            "        else:\n"
            "            return 0\n"
            "def c():\n"
            "    for x in xs:\n"
            "        if x:\n"
            "            pass\n"
        ),
    )
    result = api.analyze(tmp_path)
    assert_metric(result.metrics, "cognitive_complexity", total=6, average=2, maximum=3)
    assert_metric(
        result.metrics, "cyclomatic_complexity", total=7, average=7 / 3, maximum=3
    )
    assert_metric(result.metrics, "function_length", average=4, maximum=5)
    assert_metric(result.metrics, "nesting_depth", average=4 / 3, maximum=2)
    class_metrics = single(result, "classes", "C").metrics
    assert_metric(class_metrics, "cognitive_complexity", total=2, average=2, maximum=2)
    assert_metric(class_metrics, "function_length", average=5, maximum=5)
    for file in result.details.files:
        if Path(file.path).name == "b.py":
            assert_metric(
                file.metrics, "cognitive_complexity", total=5, average=2.5, maximum=3
            )
