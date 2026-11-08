"""API-M01〜M06/R01〜R11: 公開dataclass・詳細・変換結果の契約。"""

import copy
import json
from dataclasses import asdict, fields, is_dataclass
from typing import TYPE_CHECKING

import pytest

from .support import (
    SCOPE_FIELDS,
    PublicModel,
    assert_metric,
    save_json,
    single,
    write_source,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


@pytest.mark.parametrize(
    ("name", "expected_fields"),
    [
        (
            "AnalysisResult",
            (
                "schema_version type status scope metrics details errors "
                "unresolved metadata"
            ),
        ),
        (
            "ComparisonResult",
            (
                "schema_version type status before after differences "
                "incompatible_metrics metadata"
            ),
        ),
        ("AnalysisDetails", "files classes functions"),
        ("FileDetail", "id path metrics"),
        ("ClassDetail", "id file_id parent_id name line column metrics"),
        ("FunctionDetail", "id file_id parent_id name line column metrics"),
        ("AnalysisScope", "path file_count"),
        ("MetricResult", "total average maximum value unavailable_reason details"),
        ("CouplingMetricDetails", "dependencies"),
        ("DependencyCyclesMetricDetails", "groups"),
        ("DuplicationMetricDetails", "sloc duplicated_sloc"),
        ("MetricDifference", "before after difference change_rate"),
        ("AnalysisError", "code path message"),
        ("UnresolvedReference", "metric target reason"),
        ("IncompatibleMetric", "metric aggregation reason"),
        ("MeasurementModel", "definition_version settings"),
        ("AnalysisMetadata", "tool_version measurement_models settings"),
        ("ComparisonMetadata", "settings"),
    ],
)
def test_models_success_public_dataclasses(
    *, api: ModuleType, name: str, expected_fields: str
) -> None:
    """API-R01: 全公開モデルがdataclassで、仕様のフィールドを公開する。"""
    model = getattr(api, name)
    assert is_dataclass(model)
    assert set(expected_fields.split()) <= {field.name for field in fields(model)}


@pytest.mark.parametrize(
    "name",
    [
        "analyze",
        "compare",
        "load_analysis_result",
        "ResultStatus",
        "MetricDetails",
        "JSONValue",
    ],
)
def test_models_success_public_symbols(*, api: ModuleType, name: str) -> None:
    """API-R01: 公開関数・型エイリアスをcqaから取得できる。"""
    assert getattr(api, name) is not None


def test_models_success_analysis_types(
    *, api: ModuleType, analysis: PublicModel
) -> None:
    """API-M01/M06/R01: 返却モデルと入れ子、コレクション、計測条件を取得。"""
    assert isinstance(analysis, api.AnalysisResult)
    assert isinstance(analysis.scope, api.AnalysisScope)
    assert isinstance(analysis.details, api.AnalysisDetails)
    assert isinstance(analysis.metadata, api.AnalysisMetadata)
    assert analysis.metrics.__class__ is dict
    assert analysis.errors.__class__ is list
    assert analysis.unresolved.__class__ is list
    assert analysis.metadata.tool_version
    assert analysis.metadata.settings.__class__ is dict
    for collection, name in (
        (analysis.details.files, "FileDetail"),
        (analysis.details.classes, "ClassDetail"),
        (analysis.details.functions, "FunctionDetail"),
    ):
        assert collection.__class__ is list
        assert all(isinstance(item, getattr(api, name)) for item in collection)
    for metric, aggregations in SCOPE_FIELDS.items():
        value = analysis.metrics[metric]
        assert isinstance(value, api.MetricResult)
        model = analysis.metadata.measurement_models[metric]
        assert isinstance(model, api.MeasurementModel)
        assert model.definition_version
        assert model.settings.__class__ is dict
        for aggregation in aggregations:
            if getattr(value, aggregation) is None:
                assert value.unavailable_reason
    assert all(isinstance(error, api.AnalysisError) for error in analysis.errors)
    assert all(
        isinstance(item, api.UnresolvedReference) for item in analysis.unresolved
    )


def test_models_success_construct_and_mutate(*, api: ModuleType) -> None:
    """API-R02: モデルを公開コンストラクタで構築し、属性・辞書・リストを変更。"""
    metric = api.MetricResult(total=1)
    file = api.FileDetail(id="file", path="main.py", metrics={"sloc": metric})
    model = api.MeasurementModel(definition_version="1", settings={})
    result = api.AnalysisResult(
        schema_version="1",
        type="analysis",
        status="complete",
        scope=api.AnalysisScope(path="project", file_count=1),
        metrics={"sloc": metric},
        details=api.AnalysisDetails(files=[file]),
        errors=[],
        unresolved=[],
        metadata=api.AnalysisMetadata(
            tool_version="test", measurement_models={"sloc": model}, settings={}
        ),
    )
    result.scope.path = "changed"
    changed_total = 12
    result.metrics["sloc"].total = changed_total
    result.details.files.append(
        api.FileDetail(
            id="file2", path="second.py", metrics={"sloc": api.MetricResult(total=0)}
        )
    )
    result.metadata.measurement_models["sloc"].settings["example"] = True
    result.errors.append(
        api.AnalysisError(
            code="SYNTAX_ERROR", path="broken.py", message="Invalid syntax"
        )
    )
    result.status = "partial"
    assert result.scope.path == "changed"
    assert result.metrics["sloc"].total == changed_total
    assert {item.path for item in result.details.files} == {"main.py", "second.py"}
    assert result.metadata.measurement_models["sloc"].settings == {"example": True}
    assert result.errors[0].path == "broken.py"
    assert result.status == "partial"
    assert result.schema_version == "1"
    assert result.details.files[0].path == "main.py"


def test_analyze_success_definition_identity(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-M03/R03〜R04: フラットな定義・一意ID・直接親・定義文の位置を保持。"""
    source = (
        "@decorate\nclass 外側:\n"
        "    @staticmethod\n    def method():\n"
        "        def inner(): pass\n        class Local: pass\n"
        "    class Nested:\n        async def run(self): pass\n"
        "def same(): pass\ndef same(): pass\n"
        "class Repeated: pass\nclass Repeated: pass\n"
    )
    result = api.analyze(write_source(tmp_path, "定義.py", source))
    details = result.details
    records = details.classes + details.functions
    ids = [record.id for record in details.files + records]
    assert len(ids) == len(set(ids))
    assert len(details.classes) == source.count("class ")
    assert len(details.functions) == source.count("def ")
    assert all(record.file_id == details.files[0].id for record in records)
    outer, nested = (
        single(result, "classes", "外側"),
        single(result, "classes", "Nested"),
    )
    method = single(result, "functions", "method")
    assert all(
        record.parent_id is None
        for record in records
        if record.name in {"same", "Repeated"}
    )
    assert outer.parent_id is None
    assert method.parent_id == nested.parent_id == outer.id
    assert single(result, "functions", "inner").parent_id == method.id
    assert single(result, "classes", "Local").parent_id == method.id
    assert single(result, "functions", "run").parent_id == nested.id
    assert {(record.name, record.line, record.column) for record in records} == {
        ("外側", 2, 0),
        ("method", 4, 4),
        ("inner", 5, 8),
        ("Local", 6, 8),
        ("Nested", 7, 4),
        ("run", 8, 8),
        ("same", 9, 0),
        ("same", 10, 0),
        ("Repeated", 11, 0),
        ("Repeated", 12, 0),
    }
    assert_metric(result.metrics, "function_count", total=5)
    assert_metric(result.metrics, "class_count", total=5)
    assert_metric(details.files[0].metrics, "function_count", total=5)
    assert_metric(details.files[0].metrics, "class_count", total=5)
    assert_metric(outer.metrics, "function_count", total=1)
    assert_metric(nested.metrics, "function_count", total=1)


@pytest.mark.parametrize(
    "definition", ["def 関数(): pass", "async def 関数(): pass", "class クラス: pass"]
)
def test_analyze_success_decorated_positions(
    *, api: ModuleType, tmp_path: Path, definition: str
) -> None:
    """API-R04: デコレータ開始位置でなくdef・async def・class文位置を返す。"""
    result = api.analyze(
        write_source(tmp_path, "positions.py", "@decorate\n" + definition + "\n")
    )
    item = (
        result.details.classes
        if definition.startswith("class")
        else result.details.functions
    )[0]
    assert (item.line, item.column) == (2, 0)
    assert item.name == ("クラス" if definition.startswith("class") else "関数")


def test_serialization_success_inapplicable_fields(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-R08: Python上のNone、JSONの省略、計測不能nullと理由を区別。"""
    result = api.analyze(write_source(tmp_path, "no_functions.py"))
    assert result.metrics["sloc"].average is None
    assert result.metrics["sloc"].maximum is None
    assert result.metrics["sloc"].details is None
    document = result.to_dict()
    assert "average" not in document["metrics"]["sloc"]
    assert "maximum" not in document["metrics"]["sloc"]
    assert "details" not in document["metrics"]["sloc"]
    complexity = document["metrics"]["cyclomatic_complexity"]
    assert complexity["total"] == 0
    assert complexity["average"] is None
    assert complexity["maximum"] is None
    assert complexity["unavailable_reason"]
    assert "details" not in complexity


@pytest.mark.parametrize("comparison", [False, True])
def test_serialization_success_json_structure(
    *, api: ModuleType, analysis: PublicModel, comparison: bool
) -> None:
    """API-R09: 各状態を標準JSONで表現し、比較には両側の完全な構造を保持。"""
    result = api.compare(analysis, analysis) if comparison else analysis
    document = result.to_dict()
    assert (
        json.loads(json.dumps(document, ensure_ascii=False, allow_nan=False))
        == document
    )
    assert document["status"] == analysis.status
    if comparison:
        assert document["before"] == document["after"] == analysis.to_dict()
        assert "differences" in document
        assert "incompatible_metrics" in document
        assert "metadata" in document
    else:
        assert {
            "scope",
            "metrics",
            "details",
            "errors",
            "unresolved",
            "metadata",
        } <= document.keys()


@pytest.mark.parametrize("comparison", [False, True])
def test_serialization_success_independent_dictionary(
    *, api: ModuleType, analysis: PublicModel, comparison: bool
) -> None:
    """API-R10: 辞書の計測値・詳細・エラー・未解決・条件変更を元へ反映しない。"""
    result = api.compare(analysis, analysis) if comparison else analysis
    snapshot = copy.deepcopy(asdict(result))
    document = result.to_dict()
    target = document["before"] if comparison else document
    target["metrics"]["sloc"]["total"] = 999
    target["scope"]["path"] = "changed"
    for file in target["details"]["files"]:
        file["path"] = "changed"
        file["metrics"]["fan_out"]["details"]["dependencies"].append("changed")
        file["metrics"]["duplication_rate"]["details"]["duplicated_sloc"] = 1
    for definition in target["details"]["classes"] + target["details"]["functions"]:
        definition["name"] = "changed"
    for error in target["errors"]:
        error["message"] = "changed"
    for reference in target["unresolved"]:
        reference["reason"] = "changed"
    target["details"]["files"].clear()
    target["details"]["functions"].clear()
    target["errors"].append(
        {"code": "changed", "path": "changed", "message": "changed"}
    )
    target["unresolved"].append(
        {"metric": "changed", "target": "changed", "reason": "changed"}
    )
    target["metadata"]["measurement_models"]["sloc"]["settings"]["changed"] = True
    if comparison:
        document["after"]["metrics"]["sloc"]["total"] = 1000
        document["differences"]["sloc"]["total"]["difference"] = 999
        document["incompatible_metrics"].clear()
        document["metadata"]["settings"]["changed"] = True
    assert asdict(result) == snapshot


@pytest.mark.parametrize("entry", ["from_dict", "load"])
def test_serialization_success_roundtrip(
    *, api: ModuleType, analysis: PublicModel, tmp_path: Path, entry: str
) -> None:
    """API-R11: 全状態のScope・全単位・位置・失敗・未解決・条件を復元。"""
    document = analysis.to_dict()
    if entry == "load":
        restored = api.load_analysis_result(
            save_json(tmp_path / "saved.json", document)
        )
    else:
        restored = api.AnalysisResult.from_dict(document)
    assert asdict(restored) == asdict(analysis)


def test_serialization_success_precision(*, api: ModuleType, source: Path) -> None:
    """API-R09: 小数の保持精度は表示目的で丸めない。"""
    result = api.analyze(source)
    expected = 1.23456789
    result.metrics["function_length"].average = expected
    assert result.to_dict()["metrics"]["function_length"]["average"] == expected


def test_analyze_success_measurement_levels(*, api: ModuleType, tmp_path: Path) -> None:
    """API-M02: Function・Class・File・Scopeの適用する全項目を検証する。"""
    path = write_source(
        tmp_path, "levels.py", "class C:\n    def f(self):\n        return self.x\n"
    )
    result = api.analyze(path)
    function = single(result, "functions", "f").metrics
    class_metrics = single(result, "classes", "C").metrics
    file_metrics = result.details.files[0].metrics
    assert_metric(function, "function_length", value=2)
    assert_metric(function, "cyclomatic_complexity", value=1)
    assert_metric(function, "cognitive_complexity", value=0)
    assert_metric(function, "nesting_depth", value=0)
    for metrics in (class_metrics, file_metrics, result.metrics):
        assert_metric(metrics, "function_count", total=1)
        assert_metric(metrics, "function_length", average=2, maximum=2)
        assert_metric(metrics, "cyclomatic_complexity", total=1, average=1, maximum=1)
        assert_metric(metrics, "cognitive_complexity", total=0, average=0, maximum=0)
        assert_metric(metrics, "nesting_depth", average=0, maximum=0)
    assert_metric(class_metrics, "cbo", value=0)
    assert_metric(class_metrics, "lcom4", value=1)
    for metrics in (file_metrics, result.metrics):
        assert_metric(metrics, "sloc", total=3)
        assert_metric(metrics, "class_count", total=1)
        assert_metric(metrics, "cbo", average=0, maximum=0)
        assert_metric(metrics, "lcom4", average=1, maximum=1)
        assert_metric(metrics, "duplication_rate", value=0)
    assert_metric(file_metrics, "fan_out", value=0)
    assert_metric(result.metrics, "fan_out", average=0, maximum=0)
    assert_metric(result.metrics, "dependency_cycles", value=0)
    assert isinstance(class_metrics["cbo"].details, api.CouplingMetricDetails)
    assert isinstance(file_metrics["fan_out"].details, api.CouplingMetricDetails)
    assert isinstance(
        result.metrics["dependency_cycles"].details, api.DependencyCyclesMetricDetails
    )
    assert isinstance(
        result.metrics["duplication_rate"].details, api.DuplicationMetricDetails
    )


@pytest.mark.parametrize(
    "source",
    [
        "x = 1\n",
        "def f(): pass\n",
        "class C: pass\n",
        "class C:\n    @staticmethod\n    def f(): pass\n",
    ],
)
def test_analyze_success_unavailable_boundaries(
    *, api: ModuleType, tmp_path: Path, source: str
) -> None:
    """API-M05: 対象なしの平均・最大はNone、確定した依存なしは正常な0。"""
    result = api.analyze(write_source(tmp_path, "boundaries.py", source))
    count = source.count("def ")
    assert_metric(result.metrics, "function_count", total=count)
    if count == 0:
        assert_metric(result.metrics, "function_length", average=None, maximum=None)
        assert_metric(
            result.metrics, "cyclomatic_complexity", total=0, average=None, maximum=None
        )
    assert_metric(result.metrics, "lcom4", average=None, maximum=None)
    assert_metric(result.metrics, "fan_out", average=0, maximum=0)
    assert_metric(result.metrics, "dependency_cycles", value=0)
    assert_metric(
        result.metrics,
        "cbo",
        average=0 if "class " in source else None,
        maximum=0 if "class " in source else None,
    )


def test_models_success_comparison_types(*, api: ModuleType, source: Path) -> None:
    """API-R01: Comparisonと差分・比較不能・条件も公開dataclassで返す。"""
    analysis = api.analyze(source)
    result = api.compare(analysis, analysis)
    assert isinstance(result, api.ComparisonResult)
    assert isinstance(result.before, api.AnalysisResult)
    assert isinstance(result.after, api.AnalysisResult)
    assert isinstance(result.metadata, api.ComparisonMetadata)
    assert result.differences.__class__ is dict
    assert result.incompatible_metrics.__class__ is list
    assert all(
        isinstance(item, api.MetricDifference)
        for items in result.differences.values()
        for item in items.values()
    )
    assert all(
        isinstance(item, api.IncompatibleMetric) for item in result.incompatible_metrics
    )


def test_serialization_success_incompatible_comparison(
    *, api: ModuleType, analysis: PublicModel
) -> None:
    """API-R09: 定義が非互換の比較も状態・両側・比較不能理由をJSONで保持。"""
    after = copy.deepcopy(analysis)
    for model in after.metadata.measurement_models.values():
        model.definition_version = "unknown-definition"
    result = api.compare(analysis, after)
    document = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert document["status"] == analysis.status
    assert document["before"] == analysis.to_dict()
    assert document["after"] == after.to_dict()
    assert not document["differences"] or not any(document["differences"].values())
    assert document["incompatible_metrics"]
    assert all(item["reason"] for item in document["incompatible_metrics"])
