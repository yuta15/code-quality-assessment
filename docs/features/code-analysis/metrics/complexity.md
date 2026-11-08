# Complexity Metrics

## Overview

Complexity Metricsは、ソースコードの制御フローの複雑さや、コードを理解する際の認知的負荷を定量的に把握するための指標です。

分岐の数、制御構造の組み合わせ、ネストの深さを計測することで、複雑な処理が集中している関数や、変更・テストが難しくなる可能性のある箇所を確認できます。

以下の3つの指標を提供します。

| 指標 | 説明 | 基本計測単位 |
|---|---|---|
| Cyclomatic Complexity | 制御フローの独立した経路数 | Function |
| Cognitive Complexity | コードを理解する際の認知的負荷の推定 | Function |
| Nesting Depth | 制御構造の最大ネスト深度 | Function |

3つの指標は異なる観点から複雑さを評価します。

例えば、分岐が多くてもネストが浅い関数と、分岐は少なくても深くネストした関数では、同じような複雑度になるとは限りません。

計測単位や集計に関する共通ルールは[Metrics](./README.md)を参照してください。

## Cyclomatic Complexity

### Definition

Cyclomatic Complexity（循環的複雑度）は、プログラムの制御フローに存在する独立した経路数を表す指標です。

基本値を1とし、分岐や繰り返しなどによって制御フローが分かれるたびに値を加算します。

計測方式はMcCabeの循環的複雑度を基礎とし、Python構文の加算規則は[Radon](https://radon.readthedocs.io/en/stable/intro.html#cyclomatic-complexity)に準拠します。どの関数を独立した計測対象とするかは本仕様に従い、Radonが提供するクラス単位のスコアなどはそのまま転用しません。

### Measurement Rules

- 関数・メソッド単位で計測します。
- 分岐のない関数の値は1とします。
- `def`と`async def`を対象とします。
- `__init__`、`@staticmethod`、`@classmethod`なども通常のメソッドとして計測します。
- `lambda`式は独立した計測対象に含めません。
- クラス定義自体の複雑度は提供しません。
- ネストした関数は独立して計測し、その本体の分岐を外側の関数に加算しません。メソッド内に定義されたローカル関数も同様です。
- 関数の外側にあるモジュール本体・クラス本体の制御構造は、関数単位のスコアには算入しません。
- `match`のガード条件は、パターンの判定に加えて、ガード条件内の論理演算子による加算を適用します。`case _`が無条件のワイルドカードである場合に限り、そのcase自体の加算を0とします。

主な構文の計数規則は以下のとおりです。

| 構文 | 加算値 |
|---|---:|
| `if` | +1 |
| `elif` | +1 |
| `else` | +0 |
| `for` / `async for` | +1 |
| `while` | +1 |
| ループの`else` | +1 |
| `except` / `except*` | 各ハンドラ+1 |
| `try`の`else` | +1 |
| `finally` | +0 |
| `with` / `async with` | +1 |
| `assert` | +1 |
| 条件式 `a if condition else b` | +1 |
| `and` / `or` | 論理演算子1個につき+1 |
| 内包表記・ジェネレータ式 | `for`節・`if`節ごとに+1 |
| `match`の通常の`case` | +1 |
| ワイルドカードの`case _` | +0 |

上記以外の構文や詳細な計数条件は、採用するRadonの計算モデルに従います。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 分岐のない関数 | `1` |
| `if`のみ | `2` |
| `if`と`else` | `2` |
| `if`と`elif` | `3` |
| `if`と`and`条件 | `3` |
| `for`のみ | `2` |
| `try`と1つの`except` | `2` |
| `try`と`finally`のみ | `1` |
| 無条件の`match`とワイルドカードのみ | `1` |
| ガード付き`case` | 無条件のワイルドカードとしては扱わず、パターン判定とガード条件を評価 |
| ネストした関数の分岐 | 内側の関数に計測し、外側には加算しない |
| `async def` | 通常の関数と同様 |
| 関数が0件 | 平均・最大は`null` |

### Example

```python
def calculate(values):
    total = 0

    for value in values:
        if value > 0:
            total += value

    return total
```

計測結果：

`Cyclomatic Complexity = 3`

内訳：

| 要素 | 加算値 |
|---|---:|
| 基本値 | 1 |
| `for` | +1 |
| `if` | +1 |
| 合計 | 3 |

## Cognitive Complexity

### Definition

Cognitive Complexity（認知的複雑度）は、コードの制御フローを人間が理解する際の負荷を推定する指標です。

Cyclomatic Complexityが独立した制御経路を評価するのに対し、Cognitive Complexityは、制御フローの中断やネストによって理解が難しくなることを評価します。

計測方式は[SonarSourceのCognitive Complexity](https://www.sonarsource.com/resources/cognitive-complexity/)に準拠します。

### Measurement Rules

- 関数・メソッド単位で計測します。
- 初期値は0とします。
- 制御フローを中断する構造に対して値を加算します。
- 制御構造が深くネストするほど、追加の複雑度を加算します。
- 論理演算子の組み合わせや再帰呼び出しも計測対象とします。
- 単純なメソッド呼び出し自体は複雑度を増加させません。
- ネストした関数やデコレータ相当の構造はSonarSourceの規則に従います。関数ごとの計測値を個別に提供し、集計で同じ関数のスコアを二重計上しません。SonarSourceのネスト関数特有の加算規則はCyclomatic Complexityの規則で上書きしません。

主な計数規則は以下のとおりです。

| 構文 | 取り扱い |
|---|---|
| `if` | +1、ネストによる追加あり |
| `elif` | +1、ネストによる追加なし |
| `else` | +1、ネストによる追加なし |
| `for` / `while` | +1、ネストによる追加あり |
| `except` | +1、ネストによる追加あり |
| `finally` | 原則として加算しない |
| 条件式 | 分岐として計測し、`else`の一部は省略形として扱う |
| `and` / `or` | 同種の論理演算子の連続や切り替わりを考慮する |
| 再帰呼び出し | 複雑度を加算する |
| `match` | SonarSourceのPython向け規則に従う |

ネストによる追加がある構文では、外側の制御構造によって加算値が増えます。

例えば、ネストしていない`if`は1、1段ネストした`if`は2として計測します。

`elif`や`else`には独自の加算規則があり、単純にすべての構文へネスト深度を加算するわけではありません。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 制御構造のない関数 | `0` |
| `if`のみ | `1` |
| `if`と`else` | `2` |
| `if`の中に`if` | `3` |
| `for`の中に`if` | `3` |
| 同種の論理演算子が連続 | 演算子のまとまりとして計測 |
| `and`と`or`が混在 | 演算子の切り替わりを考慮 |
| 通常の関数呼び出し | 呼び出し自体では加算しない |
| 再帰呼び出し | 加算する |
| 関数が0件 | 平均・最大は`null` |

### Example

```python
def calculate(values):
    total = 0

    for value in values:
        if value > 0:
            total += value

    return total
```

計測結果：

`Cognitive Complexity = 3`

内訳：

| 要素 | 加算値 |
|---|---:|
| `for` | +1 |
| ネストした`if` | +2 |
| 合計 | 3 |

この例ではCyclomatic Complexityと同じ値になりますが、計算規則が異なるため、常に一致するわけではありません。

## Nesting Depth

### Definition

Nesting Depthは、関数・メソッド内に存在する制御構造の最大ネスト深度を表す指標です。

制御構造が深くなるほど、内側の処理を理解するために保持する条件や文脈が増える可能性があります。

### Measurement Rules

- 関数・メソッド単位で計測します。
- 制御構造を持たない関数の値は0とします。
- 最も外側の制御構造を深度1とします。
- 制御構造の内側に別の制御構造が存在する場合、深度を1加算します。
- 関数・クラスの定義自体は深度に含めません。
- `else`、`elif`、`except`などは、対応する制御構造と同じ階層として扱います。
- 関数内に別の関数が定義されている場合、内側の関数は独立して計測します。外側の関数の深度に内側の関数の制御構造を含めません。

ネストの対象は以下のとおりです。

| 構文 | 取り扱い |
|---|---|
| `if` / `elif` / `else` | 同一の条件分岐構造として計測 |
| `for` / `async for` | 対象 |
| `while` | 対象 |
| `try` / `except` / `else` / `finally` | 同一の例外処理構造として計測 |
| `match` / `case` | 同一の分岐構造として計測 |
| `with` / `async with` | 対象 |
| 内包表記 | 対象外 |
| 条件式 | 対象外 |
| 関数・クラス定義 | 対象外 |

`elif`は、構文上の表現にかかわらず、直前の`if`と同じ深度として扱います。

また、`except`や`finally`も、対応する`try`に対して新しいネスト階層を追加しません。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 制御構造のない関数 | `0` |
| `if`のみ | `1` |
| `if`の中に`if` | `2` |
| `if`と`elif` | `1` |
| `if`と`else` | `1` |
| `for`の中に`if` | `2` |
| `try`と`except` | `1` |
| `try`の中に`if` | `2` |
| `match`と複数の`case` | `1` |
| 内包表記のみ | `0` |
| ネストした関数 | 関数ごとに独立して計測 |
| 関数が0件 | 平均・最大は`null` |

### Example

```python
def calculate(values):
    total = 0

    for value in values:
        if value > 0:
            total += value

    return total
```

計測結果：

`Nesting Depth = 2`

内訳：

| 制御構造 | 深度 |
|---|---:|
| `for` | 1 |
| `if` | 2 |
| 最大値 | 2 |

## Aggregation

Complexity Metricsは、関数・メソッド単位の計測結果をファイルおよび解析対象全体で集計します。

| 指標 | Total | Average | Maximum |
|---|:---:|:---:|:---:|
| Cyclomatic Complexity | ○ | ○ | ○ |
| Cognitive Complexity | ○ | ○ | ○ |
| Nesting Depth | — | ○ | ○ |

平均値は対象となる関数・メソッドの計測値の算術平均とします。

最大値は対象範囲に含まれる関数・メソッドの最大計測値とします。

ネストした関数やクラス内のメソッドも、それぞれ独立した計測対象として集計します。

計測対象の関数・メソッドが存在しない場合、合計値は0、平均値および最大値は`null`とします。

集計後も、関数・メソッドごとの計測結果を取得できます。

共通の集計ルールは[Metrics — Aggregation](./README.md#aggregation)を参照してください。

## Limitations

- Cyclomatic Complexityは制御フローの複雑さを表しますが、コードの理解しやすさを直接評価するものではありません。
- Cognitive Complexityは理解負荷を推定する指標であり、実際の理解時間を測定するものではありません。
- Nesting Depthは制御構造の深さのみを評価します。分岐数や条件式の複雑さは反映しません。
- 静的解析で確認できない実行時の制御フローは計測対象外です。
- 計測モデルやそのバージョンによって結果が異なる可能性があるため、計測条件を結果に記録します。

## References

- [Radon — Cyclomatic Complexity](https://radon.readthedocs.io/en/stable/intro.html#cyclomatic-complexity)
- [Radon — API Reference](https://radon.readthedocs.io/en/stable/api.html)
- [SonarSource — Cognitive Complexity](https://www.sonarsource.com/resources/cognitive-complexity/)
- [SonarSource — Cognitive Complexity White Paper](https://www.sonarsource.com/docs/CognitiveComplexity.pdf)
- [Python — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html)