# Size Metrics

## Overview

Size Metricsは、ソースコードの規模や構成を定量的に把握するための指標です。

コードの行数、関数の長さ、関数・クラスの数を計測することで、実装間の規模の違いや、特定の関数への処理の集中を確認できます。

以下の4つの指標を提供します。

| 指標 | 説明 | 基本計測単位 |
|---|---|---|
| SLOC | コメントや空行などを除いたコード行数 | File |
| Function Length | 関数・メソッドの物理的な長さ | Function |
| Function Count | 定義された関数・メソッドの数 | File |
| Class Count | 定義されたクラスの数 | File |

計測単位と集計に関する共通ルールは[Metrics](./README.md)を参照してください。

## SLOC

### Definition

SLOC（Source Lines of Code）は、Radonの定義に基づくソースコード行数を表す指標です。

計測方式は[RadonのRaw Metrics](https://radon.readthedocs.io/en/stable/intro.html#raw-metrics)に準拠します。

### Measurement Rules

- 空行および空白文字のみの行は計数しません。
- コメントのみの行は計数しません。
- コードとコメントが同じ行に存在する場合は、コード行として計数します。
- 複数行文字列はRadonの分類規則に従い、通常のSLOCとは区別します。
- 1行に複数の文が存在しても、物理的な1行として計数します。
- ファイル単位で計測し、上位単位では対象ファイルのSLOCを合計します。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 空ファイル | `0` |
| 空行のみのファイル | `0` |
| コメントのみのファイル | `0` |
| コードと行末コメント | コード行として計数 |
| 1行に複数の文 | 1行として計数 |
| 複数行文字列 | Radonの分類規則に従う |
| 対象ファイルが0件 | 合計`0` |

### Example

```python
# Calculation utility

def add(a, b):
    return a + b  # Return result
```

計測結果：

`SLOC = 2`

コメントのみの行と空行は計数せず、関数定義と`return`文の2行を計数します。

## Function Length

### Definition

Function Lengthは、関数・メソッドが占める物理的な行数を表す指標です。

関数の開始行から終了行までを、両端を含めて計測します。

### Measurement Rules

- 関数定義行から関数本体の最終行までを計測します。
- デコレータが存在する場合は、最初のデコレータの開始行を起点とします。
- 複数行にわたる関数シグネチャを含めます。
- 関数内の空行、コメント、docstringを含めます。
- ネストした関数の定義部分も外側の関数の長さに含めます。
- ネストした関数自身の長さも個別に計測します。
- `async def`も通常の関数と同様に計測します。
- `lambda`式はFunction Lengthの計測対象に含めません。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 1行で定義された関数 | `1` |
| `pass`のみの関数 | 定義行から`pass`行までを計数 |
| `...`のみの関数 | 定義行から`...`行までを計数 |
| デコレータ付き関数 | デコレータの行を含む |
| 複数のデコレータ | すべて含む |
| 複数行の引数定義 | すべて含む |
| 関数内の空行・コメント | 含む |
| ネストした関数 | 内側・外側をそれぞれ計測 |
| `async def` | 通常の関数と同様 |
| 関数が0件 | 平均・最大は`null` |

### Example

```python
@decorator
def calculate(value):
    if value > 0:
        return value * 2
    return 0
```

計測結果：

`Function Length = 5`

デコレータ1行、関数定義1行、処理3行の合計です。

## Function Count

### Definition

Function Countは、ソースコード内に定義された関数・メソッドの数を表す指標です。

### Measurement Rules

- `def`および`async def`による定義をそれぞれ1件として計数します。
- クラス内で定義されたメソッドも含めます。
- ネストした関数も個別に計数します。ファイル・Project集計では、同一の関数定義を1回だけ計数します。
- `__init__`などの特殊メソッドを含めます。
- `@staticmethod`、`@classmethod`、`@property`などのデコレータ付きメソッドも含めます。
- 同名の関数が複数回定義されている場合、それぞれ計数します。
- `lambda`式は計数しません。
- importされた関数は計数しません。
- ファイル単位で計測し、上位単位では合計します。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 通常の`def` | 1件 |
| `async def` | 1件 |
| クラス内のメソッド | 1件 |
| ネストした関数 | 内側・外側をそれぞれ1件 |
| デコレータ付き関数 | 1件 |
| `@property`とsetter | 各定義を1件 |
| 同名関数の再定義 | 定義ごとに1件 |
| `lambda`式 | 計数しない |
| importされた関数 | 計数しない |
| 関数が存在しない | `0` |

### Example

```python
def outer():
    def inner():
        return 1
    return inner


class Service:
    def execute(self):
        pass

    async def run(self):
        pass
```

計測結果：

`Function Count = 4`

`outer`、`inner`、`execute`、`run`をそれぞれ計数します。

## Class Count

### Definition

Class Countは、ソースコード内に定義されたクラスの数を表す指標です。

### Measurement Rules

- `class`による定義を1件として計数します。
- ネストしたクラスも個別に計数します。ファイル・Project集計では、同一のクラス定義を1回だけ計数します。
- 関数内で定義されたローカルクラスも含めます。
- 同名のクラスが複数回定義されている場合、それぞれ計数します。
- 継承関係やデコレータの有無は計数に影響しません。
- importされたクラスは計数しません。
- ファイル単位で計測し、上位単位では合計します。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 通常のクラス | 1件 |
| 空のクラス | 1件 |
| 継承したクラス | 1件 |
| ネストしたクラス | 内側・外側をそれぞれ1件 |
| 関数内のクラス | 1件 |
| デコレータ付きクラス | 1件 |
| 同名クラスの再定義 | 定義ごとに1件 |
| importされたクラス | 計数しない |
| クラスが存在しない | `0` |

### Example

```python
class Outer:
    class Inner:
        pass


class Child(Outer):
    pass
```

計測結果：

`Class Count = 3`

`Outer`、`Inner`、`Child`をそれぞれ計数します。

## Aggregation

Size Metricsは、指標の性質に応じて上位単位で集計します。

| 指標 | 集計方法 |
|---|---|
| SLOC | 合計 |
| Function Length | 平均・最大 |
| Function Count | 合計 |
| Class Count | 合計 |

関数の長さを集計する場合は、対象範囲に含まれる関数・メソッドの個別の計測値から算出します。

ネストした関数は独立した計測対象として扱います。ただし、外側の関数のFunction Lengthにも内側の関数の定義部分が含まれるため、Function Lengthの合計をSLOCとして扱うことはできません。

対象が0件の場合の共通ルールは[Empty and Unavailable Results](./README.md#empty-and-unavailable-results)に従います。

## Limitations

- SLOCはコードの物理的な規模を表すものであり、処理の複雑さや実装の品質を直接評価するものではありません。
- Function Lengthはコメント・空行を含むため、実際の処理量と一致するとは限りません。
- Function CountおよびClass Countは構文上の定義数を計測します。実行時に生成される関数・クラスや、動的な再定義の結果は評価しません。
- ネストした関数・クラスも計数するため、各階層の計測値を重複して合計しないように扱います。

## References

- [Radon — Raw Metrics](https://radon.readthedocs.io/en/stable/intro.html#raw-metrics)
- [Python — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html)