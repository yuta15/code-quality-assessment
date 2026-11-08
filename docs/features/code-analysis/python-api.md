# Python API Reference

Code Analysisが公開するPython APIの仕様を定義します。

本APIは、Pythonソースコードの解析、解析結果の比較、および保存済み解析結果の読み込みを提供します。

公開関数およびデータモデルは`cqa`パッケージからインポートできます。データモデルにはPython標準ライブラリの`dataclass`を使用します。

## Functions

### `analyze()`

指定したPythonファイルまたはディレクトリを解析します。

#### Signature

```python
def analyze(
    target: str | Path,
    *,
    exclude: Sequence[str] = (),
    use_gitignore: bool = False,
) -> AnalysisResult: ...
```

#### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `target` | `str \| Path` | 必須 | 解析対象のファイルまたはディレクトリ |
| `exclude` | `Sequence[str]` | `()` | 除外対象のGlobパターン |
| `use_gitignore` | `bool` | `False` | `.gitignore`の適用有無 |

#### Returns

`AnalysisResult`

解析対象全体の計測値と、ファイル・クラス・関数の詳細結果を返します。

解析対象が0件の場合も`AnalysisResult`を返します。

個別ファイルの解析に失敗した場合は、成功したファイルの結果とエラー情報を返し、`status`を`partial`とします。

#### Raises

| Exception | Condition |
|---|---|
| `FileNotFoundError` | 解析対象が存在しない |
| `PermissionError` | 解析対象にアクセスできない |
| `ValueError` | 非対応ファイルを直接指定した |

解析対象の選択、除外条件および部分失敗の処理は[Targets](./targets.md)に従います。

### `compare()`

2つのAnalysis Resultを比較します。

#### Signature

```python
def compare(
    before: AnalysisResult,
    after: AnalysisResult,
) -> ComparisonResult: ...
```

#### Parameters

| Name | Type | Description |
|---|---|---|
| `before` | `AnalysisResult` | 比較元の解析結果 |
| `after` | `AnalysisResult` | 比較先の解析結果 |

#### Returns

`ComparisonResult`

Analysis Scope全体の集計値について、差分・変化率および比較不能な項目の情報を返します。

ファイル・クラス・関数の個別対応付けは行いません。

比較可能な指標が0件の場合も`ComparisonResult`を返します。

`compare()`は、受け取った`AnalysisResult`を変更しません。

#### Raises

| Exception | Condition |
|---|---|
| `TypeError` | 引数が`AnalysisResult`ではない |

指標の非互換や計測不能値は例外とせず、結果に保持します。

比較規則は[Comparison](./comparison.md)に従います。

### `load_analysis_result()`

保存済みのAnalysis Result JSONを読み込みます。

#### Signature

```python
def load_analysis_result(
    path: str | Path,
) -> AnalysisResult: ...
```

#### Parameters

| Name | Type | Description |
|---|---|---|
| `path` | `str \| Path` | Analysis Result JSONのファイルパス |

#### Returns

`AnalysisResult`

保存された計測値、解析対象、詳細結果、エラー、未解決情報およびメタデータを復元します。

元のソースコードの再解析は行いません。

#### Raises

| Exception | Condition |
|---|---|
| `FileNotFoundError` | 指定ファイルが存在しない |
| `PermissionError` | 指定ファイルを読み取れない |
| `ValueError` | JSONが不正、非対応スキーマ、またはAnalysis Resultとして不正 |

Comparison Result JSONは読み込み対象外です。

JSONスキーマは[Output](./output.md)に従います。

---

## Result Classes

解析結果と比較結果を表す公開クラスです。

各クラスは通常の`@dataclass`で定義します。公開フィールドの変更を禁止せず、コレクションには`dict`と`list`を使用します。

### `AnalysisResult`

ソースコードの解析結果を表します。

#### Definition

```python
@dataclass
class AnalysisResult:
    schema_version: str
    type: Literal["analysis"]
    status: ResultStatus
    scope: AnalysisScope
    metrics: dict[str, MetricResult]
    details: AnalysisDetails
    errors: list[AnalysisError]
    unresolved: list[UnresolvedReference]
    metadata: AnalysisMetadata
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `schema_version` | `str` | 結果スキーマのバージョン |
| `type` | `Literal["analysis"]` | 結果種別 |
| `status` | `ResultStatus` | 解析状態 |
| `scope` | `AnalysisScope` | 解析対象の情報 |
| `metrics` | `dict[str, MetricResult]` | Analysis Scope全体の計測値 |
| `details` | `AnalysisDetails` | 個別ファイル・クラス・関数の計測結果 |
| `errors` | `list[AnalysisError]` | 解析エラー |
| `unresolved` | `list[UnresolvedReference]` | 未解決情報 |
| `metadata` | `AnalysisMetadata` | 計測条件・バージョン情報 |

#### Methods

##### `to_dict()`

```python
def to_dict(self) -> dict[str, Any]: ...
```

Analysis ResultをJSON互換の辞書へ変換します。

数値の表示用丸めは行いません。返却する辞書は、元の結果オブジェクトから独立しています。

##### `from_dict()`

```python
@classmethod
def from_dict(
    cls,
    data: Mapping[str, Any],
) -> AnalysisResult: ...
```

JSON互換の辞書を検証し、Analysis Resultを生成します。

不正な構造または非対応スキーマの場合は`ValueError`を送出します。

### `ComparisonResult`

2つの解析結果の比較を表します。

#### Definition

```python
@dataclass
class ComparisonResult:
    schema_version: str
    type: Literal["comparison"]
    status: ResultStatus
    before: AnalysisResult
    after: AnalysisResult
    differences: dict[str, dict[str, MetricDifference]]
    incompatible_metrics: list[IncompatibleMetric]
    metadata: ComparisonMetadata
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `schema_version` | `str` | 結果スキーマのバージョン |
| `type` | `Literal["comparison"]` | 結果種別 |
| `status` | `ResultStatus` | 比較状態 |
| `before` | `AnalysisResult` | 比較元の解析結果 |
| `after` | `AnalysisResult` | 比較先の解析結果 |
| `differences` | `dict[str, dict[str, MetricDifference]]` | 指標・集計項目ごとの差分 |
| `incompatible_metrics` | `list[IncompatibleMetric]` | 比較不能な指標・集計項目 |
| `metadata` | `ComparisonMetadata` | 比較条件 |

#### Methods

##### `to_dict()`

```python
def to_dict(self) -> dict[str, Any]: ...
```

Comparison ResultをJSON互換の辞書へ変換します。

`before`と`after`は、それぞれ完全なAnalysis Resultとして含めます。

---

## Detail Classes

解析対象の個別計測結果を表す公開クラスです。

ファイル・クラス・関数はそれぞれ独立したコレクションに格納し、IDで所属関係を表現します。

### `AnalysisDetails`

ファイル・クラス・関数の詳細結果を保持します。

#### Definition

```python
@dataclass
class AnalysisDetails:
    files: list[FileDetail] = field(default_factory=list)
    classes: list[ClassDetail] = field(default_factory=list)
    functions: list[FunctionDetail] = field(default_factory=list)
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `files` | `list[FileDetail]` | ファイル単位の計測結果 |
| `classes` | `list[ClassDetail]` | クラス単位の計測結果 |
| `functions` | `list[FunctionDetail]` | 関数・メソッド単位の計測結果 |

各コレクションはフラットな構造とします。

関数やクラスを親要素の内部に重複して格納しません。

### `FileDetail`

個別ファイルの計測結果を表します。

#### Definition

```python
@dataclass
class FileDetail:
    id: str
    path: str
    metrics: dict[str, MetricResult]
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `id` | `str` | ファイルの識別子 |
| `path` | `str` | ファイルパス |
| `metrics` | `dict[str, MetricResult]` | ファイル単位の計測値 |

`id`は同一Analysis Result内で一意です。

### `ClassDetail`

個別クラスの計測結果を表します。

#### Definition

```python
@dataclass
class ClassDetail:
    id: str
    file_id: str
    parent_id: str | None
    name: str
    line: int
    column: int
    metrics: dict[str, MetricResult]
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `id` | `str` | クラス定義の識別子 |
| `file_id` | `str` | 定義元ファイルのID |
| `parent_id` | `str \| None` | 直接の親となる関数・クラスのID |
| `name` | `str` | クラス名 |
| `line` | `int` | `class`文の開始行 |
| `column` | `int` | `class`文の開始列 |
| `metrics` | `dict[str, MetricResult]` | クラス単位の計測値 |

ネストクラスや関数内で定義されたローカルクラスも、それぞれ独立した`ClassDetail`として格納します。

### `FunctionDetail`

個別関数・メソッドの計測結果を表します。

#### Definition

```python
@dataclass
class FunctionDetail:
    id: str
    file_id: str
    parent_id: str | None
    name: str
    line: int
    column: int
    metrics: dict[str, MetricResult]
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `id` | `str` | 関数定義の識別子 |
| `file_id` | `str` | 定義元ファイルのID |
| `parent_id` | `str \| None` | 直接の親となる関数・クラスのID |
| `name` | `str` | 関数・メソッド名 |
| `line` | `int` | `def`・`async def`文の開始行 |
| `column` | `int` | 定義文の開始列 |
| `metrics` | `dict[str, MetricResult]` | 関数単位の計測値 |

通常関数、非同期関数、メソッド、ネスト関数は、それぞれ独立した`FunctionDetail`として格納します。

### 識別子と所属関係

各IDは同一Analysis Result内で一意とします。

| Field | Rule |
|---|---|
| `id` | 定義位置を識別できる一意なID |
| `file_id` | `AnalysisDetails.files`内の既存IDを参照 |
| `parent_id` | 直接の親となる`ClassDetail`または`FunctionDetail`のIDを参照 |
| `parent_id = None` | ファイル直下に定義された要素 |

IDは文字列として公開します。利用者はID文字列の内部形式を解析せず、識別と関連付けに使用します。

行番号は1始まり、列番号は0始まりです。列番号はソース行におけるUTF-8バイトオフセットとします。

同名の関数・クラスであっても、異なる定義位置は別のIDを持ちます。

あるクラスに直接所属するメソッドは、そのクラスのIDを`parent_id`として保持します。

関数内のネスト関数やローカルクラスは、外側の関数IDを`parent_id`として保持します。

個別定義はそれぞれ1回だけ格納します。

---

## Value Classes

### `ResultStatus`

解析・比較の状態を表します。

```python
ResultStatus = Literal["complete", "partial"]
```

| Value | Description |
|---|---|
| `complete` | 対象ファイルの解析がすべて成功 |
| `partial` | 一部の対象ファイルで解析に失敗 |

未解決依存が存在することだけを理由として`partial`にはしません。

### `AnalysisScope`

解析対象の情報を表します。

```python
@dataclass
class AnalysisScope:
    path: str
    file_count: int
```

| Name | Type | Description |
|---|---|---|
| `path` | `str` | 指定された解析対象 |
| `file_count` | `int` | 解析対象として選択されたファイル数 |

ファイル数には、選択された後に個別の解析で失敗したファイルも含みます。

### `MetricResult`

指標の計測値または集計値を表します。

```python
@dataclass
class MetricResult:
    total: int | float | None = None
    average: float | None = None
    maximum: int | float | None = None
    value: int | float | None = None
    unavailable_reason: str | None = None
    details: MetricDetails | None = None
```

#### Attributes

| Name | Type | Description |
|---|---|---|
| `total` | `int \| float \| None` | 合計値 |
| `average` | `float \| None` | 平均値 |
| `maximum` | `int \| float \| None` | 最大値 |
| `value` | `int \| float \| None` | 個別計測値 |
| `unavailable_reason` | `str \| None` | 計測不能な理由 |
| `details` | `MetricDetails \| None` | 指標固有の詳細情報 |

`details`には、依存先一覧、循環依存グループ、重複行数など、単一の数値では表現できない情報を保持します。指標に固有の詳細情報がない場合は`None`とします。

#### 集計項目の取り扱い

各指標で使用する集計項目は[Metrics](./metrics/README.md)に従います。

Python APIでは、適用対象外の集計項目を`None`として保持します。ただし、**適用対象外であることは、指標と計測単位に適用される集計規則によって判定します。**

JSONへの変換時には、適用対象外の集計項目を出力しません。

一方、適用対象であるにもかかわらず計測できない項目は、JSONに`null`として出力し、その理由を保持します。

例えば、関数が存在しない場合の平均Cyclomatic Complexityは次のようになります。

```json
{
  "cyclomatic_complexity": {
    "total": 0,
    "average": null,
    "maximum": null,
    "unavailable_reason": "NO_FUNCTIONS"
  }
}
```

SLOCのように合計値のみを提供する指標では、適用対象外の`average`や`maximum`をJSONに含めません。

```json
{
  "sloc": {
    "total": 100
  }
}
```

### `MetricDetails`

指標固有の詳細情報の共通型です。

```python
MetricDetails: TypeAlias = (
    CouplingMetricDetails
    | DependencyCyclesMetricDetails
    | DuplicationMetricDetails
)
```

`MetricResult.details`の型は、指標識別子に応じて決まります。

| 指標 | 計測単位 | 詳細データ型 |
|---|---|---|
| CBO | Class | `CouplingMetricDetails` |
| Fan-out | File | `CouplingMetricDetails` |
| Dependency Cycles | Analysis Scope | `DependencyCyclesMetricDetails` |
| Duplication Rate | File・Analysis Scope | `DuplicationMetricDetails` |

CBO・Fan-outのFile・Analysis Scope集計には、個別要素の依存先を重複して集約しません。依存先は各Class・Fileの詳細結果から取得します。

#### `CouplingMetricDetails`

CBOおよびFan-outで確定できた依存先を保持します。

```python
@dataclass
class CouplingMetricDetails:
    dependencies: list[str]
```

| Name | Type | Description |
|---|---|---|
| `dependencies` | `list[str]` | 重複を除いた確定依存先の識別子 |

CBOでは依存先クラス、Fan-outでは依存先モジュールを保持します。解析対象内のクラスは`ClassDetail.id`で参照します。解析対象外のクラスとモジュールは、識別できた依存先を一意に区別できる文字列で表現します。文字列の内部形式には依存しません。

依存の方向は計測元から依存先への一方向です。未解決の参照はこの一覧に含めず、`AnalysisResult.unresolved`へ記録します。

#### `DependencyCyclesMetricDetails`

循環依存グループの構成モジュールを保持します。

```python
@dataclass
class DependencyCyclesMetricDetails:
    groups: list[list[str]]
```

| Name | Type | Description |
|---|---|---|
| `groups` | `list[list[str]]` | 強連結成分ごとの構成モジュールの識別子 |

各文字列は`FileDetail.id`を参照します。1グループには2つ以上の異なるモジュールを含めます。各グループに含まれるモジュールは重複せず、同じモジュールが複数のグループに現れることもありません。

循環依存グループ数は`MetricResult.value`に保持します。`groups`の要素数と一致します。循環依存が存在しない場合は`value=0`、`groups=[]`です。

#### `DuplicationMetricDetails`

Duplication Rateの算出に使用したSLOCを保持します。

```python
@dataclass
class DuplicationMetricDetails:
    sloc: int
    duplicated_sloc: int
```

| Name | Type | Description |
|---|---|---|
| `sloc` | `int` | 重複率の分母となるSLOC |
| `duplicated_sloc` | `int` | 重複と判定されたSLOC対象行数 |

`MetricResult.value`には百分率（0〜100）または計測不能時の`None`を保持します。`sloc`が0の場合も`duplicated_sloc=0`を保持し、率は`None`と理由を返します。

ファイル単位では、他の解析対象ファイルとの重複も`duplicated_sloc`に含めます。Analysis Scope単位では、各成功ファイルの`sloc`・`duplicated_sloc`の合計を使用して重複率を算出します。重複SLOCは同じ行を二重計上しません。

### `MetricDifference`

比較した計測項目の値を表します。

```python
@dataclass
class MetricDifference:
    before: int | float | None
    after: int | float | None
    difference: int | float | None
    change_rate: float | None
```

| Name | Type | Description |
|---|---|---|
| `before` | `int \| float \| None` | 比較元の値 |
| `after` | `int \| float \| None` | 比較先の値 |
| `difference` | `int \| float \| None` | After − Before |
| `change_rate` | `float \| None` | Before基準の変化率（%） |

差分・変化率の計算規則は[Comparison](./comparison.md)に従います。

### `AnalysisError`

ファイル解析の失敗を表します。

```python
@dataclass
class AnalysisError:
    code: str
    path: str
    message: str
```

| Name | Type | Description |
|---|---|---|
| `code` | `str` | エラーコード |
| `path` | `str` | 対象パス |
| `message` | `str` | エラーの説明 |

エラーコードは[Targets](./targets.md)に従います。

### `UnresolvedReference`

静的解析で解決できなかった情報を表します。

```python
@dataclass
class UnresolvedReference:
    metric: str
    target: str
    reason: str
```

| Name | Type | Description |
|---|---|---|
| `metric` | `str` | 関連する指標の識別子 |
| `target` | `str` | 未解決情報が発生した計測対象のID |
| `reason` | `str` | 未解決の理由 |

### `IncompatibleMetric`

比較不能な指標または集計項目を表します。

```python
@dataclass
class IncompatibleMetric:
    metric: str
    aggregation: str | None
    reason: str
```

| Name | Type | Description |
|---|---|---|
| `metric` | `str` | 指標識別子 |
| `aggregation` | `str \| None` | 比較不能な集計項目。指標全体の場合は`None` |
| `reason` | `str` | 比較不能な理由 |

同じ指標のAverageは比較可能でもMaximumのみ比較不能な場合、該当する集計項目だけを区別します。

---

## Metadata Classes

### `MeasurementModel`

各指標の計測定義と設定を表します。

```python
@dataclass
class MeasurementModel:
    definition_version: str
    settings: dict[str, JSONValue]
```

| Name | Type | Description |
|---|---|---|
| `definition_version` | `str` | 計測定義のバージョン |
| `settings` | `dict[str, JSONValue]` | 計測値に影響する設定 |

### `AnalysisMetadata`

解析時の条件およびバージョン情報を表します。

```python
@dataclass
class AnalysisMetadata:
    tool_version: str
    measurement_models: dict[str, MeasurementModel]
    settings: dict[str, JSONValue]
```

| Name | Type | Description |
|---|---|---|
| `tool_version` | `str` | 解析ツールのバージョン |
| `measurement_models` | `dict[str, MeasurementModel]` | 指標ごとの計測定義と設定 |
| `settings` | `dict[str, JSONValue]` | 解析全体の設定 |

### `ComparisonMetadata`

比較実行時に使用した条件を保持します。

```python
@dataclass
class ComparisonMetadata:
    settings: dict[str, JSONValue]
```

### `JSONValue`

JSONとして表現できる値の型です。

```python
JSONValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)
```

---

## Serialization

公開結果モデルはJSON互換の辞書への変換をサポートします。

`AnalysisResult.to_dict()`および`ComparisonResult.to_dict()`は、各公開モデルをJSONで表現できる構造に変換します。

返却した辞書およびその内部コレクションは元の結果オブジェクトから独立しており、辞書の変更によって元の結果は変更されません。

`AnalysisDetails`は以下の3つの配列として出力します。

```json
{
  "details": {
    "files": [],
    "classes": [],
    "functions": []
  }
}
```

各要素のフィールド名は対応する公開クラスの属性名と一致します。

`MetricResult.details`が`None`の場合、JSONには`details`フィールドを出力しません。指標固有の詳細がある場合は、対応する詳細クラスのフィールドを`details`オブジェクト内に出力します。

例えば、依存先・循環依存グループ・重複率の詳細は次の形で表します。

```json
{
  "cbo": {
    "value": 1,
    "details": {"dependencies": ["class-id"]}
  },
  "dependency_cycles": {
    "value": 1,
    "details": {"groups": [["file-a-id", "file-b-id"]]}
  },
  "duplication_rate": {
    "value": 20.0,
    "details": {"sloc": 100, "duplicated_sloc": 20}
  }
}
```

この例は各指標のデータ構造を示したものであり、実際の出力ではCBOはClass、Dependency CyclesはAnalysis Scopeなど、定義された計測単位の結果に配置します。

`list`はJSON配列、`None`は`null`として表現します。

保存したAnalysis Resultは、`load_analysis_result()`または`AnalysisResult.from_dict()`で復元できます。

復元時には以下の情報を保持します。

- Analysis Scopeと個別ファイル・クラス・関数の識別情報
- 各計測単位の値と集計値
- 定義位置と親子関係
- エラーおよび未解決情報
- 計測条件とバージョン
- 解析状態

数値には表示目的の丸めを適用しません。

JSONのスキーマ、保存形式および互換性については[Output](./output.md)に従います。

## Related Documents

- [Usage](./usage.md)
- [Targets](./targets.md)
- [Metrics](./metrics/README.md)
- [Comparison](./comparison.md)
- [Output](./output.md)