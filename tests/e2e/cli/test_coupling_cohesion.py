"""CLI-M04〜M05: 依存の向き、循環群、LCOM4の接続規則。"""

import textwrap
from pathlib import Path

import pytest

from .support import CLI, assert_metric, single, write_source


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("pass", 0),
        ("def f(self):\n    return A()", 0),
        ("def f(self):\n    return B()", 1),
        ("def f(self):\n    return B(), C()", 2),
    ],
)
def test_analyze_success_cbo(
    *, cli: CLI, tmp_path: Path, body: str, expected: int
) -> None:
    """CLI-M04/API-C01: 自己参照を除き、別クラス定義を数える。"""
    source = (
        "class B: pass\nclass C: pass\nclass A:\n"
        + textwrap.indent(body, "    ")
        + "\n"
    )
    result = cli.analyze(write_source(tmp_path, "classes.py", source))
    item = single(result, "classes", "A")["metrics"]["cbo"]
    assert item["value"] == expected
    assert len(set(item["details"]["dependencies"])) == expected
    assert_metric(single(result, "classes", "B")["metrics"], "cbo", value=0)


def test_analyze_success_cbo_deduplicates_forms(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-M04/API-C02: 継承・注釈・生成・属性・呼び出しは同一依存先。"""
    source = (
        "class B:\n"
        "    field = 1\n"
        "    def run(self): pass\n"
        "class A(B):\n"
        "    item: B\n"
        "    def f(self, b: B) -> B:\n"
        "        B().run()\n"
        "        return B.field\n"
    )
    result = cli.analyze(write_source(tmp_path, "forms.py", source))
    a, b = single(result, "classes", "A"), single(result, "classes", "B")
    assert a["metrics"]["cbo"]["details"]["dependencies"] == [b["id"]]
    assert_metric(a["metrics"], "cbo", value=1)
    assert_metric(b["metrics"], "cbo", value=0)
    assert "details" not in result["metrics"]["cbo"]


def test_analyze_success_dependencies_distinguish_definitions(
    *, cli: CLI, tmp_path: Path
) -> None:
    """CLI-M04/API-C03〜C05: 同名別定義を区別し、import別名を重複計数しない。"""
    _ = write_source(tmp_path, "one.py", "class Same: pass\n")
    _ = write_source(tmp_path, "two.py", "class Same: pass\n")
    _ = write_source(
        tmp_path,
        "consumer.py",
        (
            "from one import Same as First\n"
            "from one import Same as Alias\n"
            "from two import Same as Second\n"
            "class Local: pass\n"
            "class Consumer(First, Alias, Second, Local): pass\n"
        ),
    )
    result = cli.analyze(tmp_path)
    consumer = single(result, "classes", "Consumer")
    targets = {
        item["id"]
        for item in result["details"]["classes"]
        if item["name"] in {"Same", "Local"}
    }
    assert set(consumer["metrics"]["cbo"]["details"]["dependencies"]) == targets
    assert_metric(consumer["metrics"], "cbo", value=3)
    assert_metric(result["metrics"], "cbo", average=0.75, maximum=3)
    file = next(
        item
        for item in result["details"]["files"]
        if Path(item["path"]).name == "consumer.py"
    )
    assert_metric(file["metrics"], "fan_out", value=2)
    assert_metric(result["metrics"], "fan_out", average=2 / 3, maximum=2)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1\n", 0),
        ("import main\n", 0),
        ("from pathlib import Path, PurePath\nimport pathlib as alias\n", 1),
        ("import json\nimport logging\nimport pathlib\n", 3),
    ],
)
def test_analyze_success_fan_out(
    *, cli: CLI, tmp_path: Path, source: str, expected: int
) -> None:
    """CLI-M04/API-C06〜C07: 標準モジュールも計数し、自己・同一依存を除く。"""
    result = cli.analyze(write_source(tmp_path, "main.py", source))
    metric = result["details"]["files"][0]["metrics"]["fan_out"]
    assert metric["value"] == expected
    assert len(set(metric["details"]["dependencies"])) == expected
    assert "details" not in result["metrics"]["fan_out"]


@pytest.mark.parametrize(
    "statement",
    [
        "import package.dep\nimport package.dep as alias\n",
        "from . import dep\nfrom .dep import B\n",
        "from package import dep\n",
    ],
)
def test_analyze_success_package_imports(
    *, cli: CLI, tmp_path: Path, statement: str
) -> None:
    """CLI-M04/API-C05/C08: 絶対・相対・from importは定義元モジュールを参照。"""
    _ = write_source(tmp_path, "package/__init__.py", "")
    _ = write_source(tmp_path, "package/dep.py", "class B: pass\n")
    _ = write_source(tmp_path, "package/consumer.py", statement)
    result = cli.analyze(tmp_path)
    file = next(
        item
        for item in result["details"]["files"]
        if Path(item["path"]).name == "consumer.py"
    )
    assert_metric(file["metrics"], "fan_out", value=1)


@pytest.mark.parametrize(
    ("edges", "groups"),
    [
        ({"a": (), "b": ()}, []),
        ({"a": ("b",), "b": ("c",), "c": ()}, []),
        ({"a": ("a",)}, []),
        ({"a": ("b",), "b": ("a",)}, [{"a", "b"}]),
        ({"a": ("b",), "b": ("c",), "c": ("a",)}, [{"a", "b", "c"}]),
        ({"a": ("b", "c"), "b": ("a", "c"), "c": ("a",)}, [{"a", "b", "c"}]),
        (
            {"a": ("b",), "b": ("a",), "c": ("d",), "d": ("c",)},
            [{"a", "b"}, {"c", "d"}],
        ),
        (
            {"a": ("b",), "b": ("a", "c"), "c": ("d",), "d": ("c",)},
            [{"a", "b"}, {"c", "d"}],
        ),
        (
            {"a": ("b",), "b": ("a", "c"), "c": ("d",), "d": ("c", "a")},
            [{"a", "b", "c", "d"}],
        ),
    ],
)
def test_analyze_success_dependency_cycles(
    *,
    cli: CLI,
    tmp_path: Path,
    edges: dict[str, tuple[str, ...]],
    groups: list[set[str]],
) -> None:
    """CLI-M04/API-C11〜C13/O21: 経路数ではなく強連結群をFile IDで表す。"""
    for module, targets in edges.items():
        _ = write_source(
            tmp_path,
            f"{module}.py",
            "".join(f"import {target}\n" for target in targets),
        )
    result = cli.analyze(tmp_path)
    ids = {item["id"]: Path(item["path"]).stem for item in result["details"]["files"]}
    metric = result["metrics"]["dependency_cycles"]
    assert metric["value"] == len(groups)
    actual = metric["details"]["groups"]
    assert {frozenset(ids[ident] for ident in group) for group in actual} == {
        frozenset(group) for group in groups
    }
    flat = [ident for group in actual for ident in group]
    assert len(flat) == len(set(flat))


def test_analyze_success_cycle_excludes_outside_module(
    *, cli: CLI, tmp_path: Path
) -> None:
    """CLI-M04/API-C14: 対象外依存はFan-outに含めるが循環グループに含めない。"""
    _ = write_source(tmp_path, "a.py", "import b\n")
    _ = write_source(tmp_path, "b.py", "import a\n")
    result = cli.analyze(tmp_path, "--exclude", "b.py")
    assert_metric(result["metrics"], "dependency_cycles", value=0)
    assert_metric(result["metrics"], "fan_out", average=1, maximum=1)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("pass", None),
        ("def a(self): pass", 1),
        ("def a(self): pass\ndef b(self): pass\ndef c(self): pass", 3),
        ("def a(self): return self.x\ndef b(self): return self.x", 1),
        ("def a(self): self.x = 1\ndef b(self): self.x = 2", 1),
        ("def a(self): return self.x\ndef b(self): self.x = 2", 1),
        ("def a(self): return self.x\ndef b(self): return self.y", 2),
        ("def a(self): self.b()\ndef b(self): pass", 1),
        ("def a(self): self.b(); self.b()\ndef b(self): pass", 1),
        ("def a(self): self.a()\ndef b(self): pass", 2),
        ("def a(self): self.b()\ndef b(self): self.c()\ndef c(self): pass", 1),
        (
            (
                "def a(self): self.b()\n"
                "def b(self): pass\n"
                "def c(self): self.d()\n"
                "def d(self): pass"
            ),
            2,
        ),
        ("def a(self): return self.x, self.x\ndef b(self): return self.x", 1),
        ("def __init__(self): self.x = 0", None),
        ("@staticmethod\ndef a(): pass", None),
        ("@classmethod\ndef a(cls): pass", None),
        (
            (
                "def __init__(self): self.x = 0\n"
                "def a(self): return self.x\n"
                "def b(self): return self.x"
            ),
            1,
        ),
        ("x = 1\ndef a(self): return C.x\ndef b(self): return C.x", 2),
        ("def a(self): x = 1\ndef b(self): x = 1", 2),
        (
            (
                "def a(self): return getattr(self, input())\n"
                "def b(self): return getattr(self, input())"
            ),
            2,
        ),
        ("def a(self):\n    def inner(): return self.x\ndef b(self): return self.x", 2),
        ("def a(self):\n    def inner(): self.b()\ndef b(self): pass", 2),
        (
            (
                "def __init__(self): self.a(); self.b()\n"
                "def a(self): pass\n"
                "def b(self): pass"
            ),
            2,
        ),
        ("def a(self): other.b()\ndef b(self): pass", 2),
        ("def a(self): getattr(self, input())()\ndef b(self): pass", 2),
    ],
)
def test_analyze_success_lcom4_connections(
    *, cli: CLI, tmp_path: Path, body: str, expected: int | None
) -> None:
    """CLI-M05/API-H01〜H07/H09〜H10/H13〜H14: 属性と呼び出しの独立性。"""
    source = "class C:\n" + textwrap.indent(body, "    ") + "\n"
    result = cli.analyze(write_source(tmp_path, "cohesion.py", source))
    assert_metric(single(result, "classes", "C")["metrics"], "lcom4", value=expected)
    assert_metric(result["metrics"], "lcom4", average=expected, maximum=expected)


@pytest.mark.parametrize(
    ("access", "accessor"),
    [("return self.p", "getter"), ("self.p = 1", "setter"), ("del self.p", "deleter")],
)
def test_analyze_success_property_accessors(
    *, cli: CLI, tmp_path: Path, access: str, accessor: str
) -> None:
    """CLI-M05/API-H11: 各propertyアクセスを対応アクセサだけに接続する。"""
    definitions = {
        "getter": "@property\ndef p(self): return 1",
        "setter": "@p.setter\ndef p(self, value): pass",
        "deleter": "@p.deleter\ndef p(self): pass",
    }
    # getterはpropertyを作るため常に存在し、他アクセサとは属性共有しない。
    body = definitions["getter"]
    if accessor != "getter":
        body += "\n" + definitions[accessor]
    body += "\ndef use(self): " + access
    result = cli.analyze(
        write_source(
            tmp_path, "property.py", "class C:\n" + textwrap.indent(body, "    ") + "\n"
        )
    )
    assert_metric(
        single(result, "classes", "C")["metrics"],
        "lcom4",
        value=1 if accessor == "getter" else 2,
    )


@pytest.mark.parametrize("access", ["self.p = 1", "del self.p"])
def test_analyze_success_property_missing_accessor(
    *, cli: CLI, tmp_path: Path, access: str
) -> None:
    """CLI-M05/API-H12: 存在しないsetter/deleterへの接続を作らない。"""
    body = "@property\ndef p(self): return 1\ndef use(self): " + access
    result = cli.analyze(
        write_source(
            tmp_path, "property.py", "class C:\n" + textwrap.indent(body, "    ") + "\n"
        )
    )
    assert_metric(single(result, "classes", "C")["metrics"], "lcom4", value=2)


def test_analyze_success_nested_classes_and_nullable_aggregation(
    *, cli: CLI, tmp_path: Path
) -> None:
    """CLI-M05/API-H08/H15: 内側クラスは独立、nullを集計の分母から除く。"""
    source = (
        "class Outer:\n"
        "    class One:\n"
        "        def a(self): pass\n"
        "class Three:\n"
        "    def a(self): pass\n"
        "    def b(self): pass\n"
        "    def c(self): pass\n"
    )
    result = cli.analyze(write_source(tmp_path, "nested.py", source))
    assert_metric(single(result, "classes", "Outer")["metrics"], "lcom4", value=None)
    assert_metric(single(result, "classes", "One")["metrics"], "lcom4", value=1)
    assert_metric(single(result, "classes", "Three")["metrics"], "lcom4", value=3)
    assert_metric(result["metrics"], "lcom4", average=2, maximum=3)


@pytest.mark.parametrize("override", [False, True])
def test_analyze_success_inherited_methods(
    *, cli: CLI, tmp_path: Path, override: bool
) -> None:
    """CLI-M05/API-H07/H09/H14: 継承メソッドを頂点や橋渡しに使わない。"""
    source = (
        "class Base:\n"
        "    def __init__(self): self.x = 1\n"
        "    def bridge(self): self.a(); self.b()\n"
        "class C(Base):\n"
    )
    body = (
        "def a(self): return self.x\ndef b(self): return self.x" if override else "pass"
    )
    result = cli.analyze(
        write_source(
            tmp_path, "inherit.py", source + textwrap.indent(body, "    ") + "\n"
        )
    )
    assert_metric(
        single(result, "classes", "C")["metrics"],
        "lcom4",
        value=1 if override else None,
    )


def test_analyze_success_same_name_local_classes(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-M04/API-C04: 同一モジュールでも別位置の同名定義を統合しない。"""
    source = (
        "class Same: pass\n"
        "class First(Same): pass\n"
        "class Same: pass\n"
        "class Second(Same): pass\n"
    )
    result = cli.analyze(write_source(tmp_path, "redefined.py", source))
    definitions = sorted(
        (item for item in result["details"]["classes"] if item["name"] == "Same"),
        key=lambda item: item["line"],
    )
    for name, target in zip(("First", "Second"), definitions, strict=True):
        assert single(result, "classes", name)["metrics"]["cbo"]["details"][
            "dependencies"
        ] == [target["id"]]


@pytest.mark.parametrize(
    ("source", "fan_out", "unresolved"),
    [
        ("__import__(input())\n", 0, True),
        ("def f(obj):\n    return obj.field\n", 0, False),
        ("class Same: pass\ndef f(Same):\n    return Same()\n", 0, False),
    ],
)
def test_analyze_success_dynamic_dependency_boundary(
    *, cli: CLI, tmp_path: Path, source: str, fan_out: int, unresolved: bool
) -> None:
    """CLI-M04/API-C09〜C10: 動的importと一般の属性アクセスを区別する。"""
    result = cli.analyze(write_source(tmp_path, "dynamic.py", source))
    assert_metric(result["metrics"], "fan_out", average=fan_out, maximum=fan_out)
    assert bool(result["unresolved"]) == unresolved


def test_analyze_success_inherited_bridge_is_excluded(
    *, cli: CLI, tmp_path: Path
) -> None:
    """CLI-M05/API-H14: 継承メソッドを介して対象メソッドを接続しない。"""
    source = (
        "class Base:\n"
        "    def bridge(self): pass\n"
        "class C(Base):\n"
        "    def a(self): self.bridge()\n"
        "    def b(self): self.bridge()\n"
    )
    result = cli.analyze(write_source(tmp_path, "inherit.py", source))
    assert_metric(single(result, "classes", "C")["metrics"], "lcom4", value=2)


def test_analyze_success_from_import_attribute(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-M04/API-C08: import先の属性はその定義元モジュールを計数。"""
    _ = write_source(tmp_path, "package/__init__.py", "value = 1\n")
    _ = write_source(tmp_path, "consumer.py", "from package import value\n")
    result = cli.analyze(tmp_path)
    consumer = next(
        item
        for item in result["details"]["files"]
        if Path(item["path"]).name == "consumer.py"
    )
    assert_metric(consumer["metrics"], "fan_out", value=1)
