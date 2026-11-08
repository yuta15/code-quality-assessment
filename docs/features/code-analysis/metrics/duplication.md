# Duplication Metrics

## Overview

Duplication Metricsは、ソースコード内に同一または類似した記述がどの程度存在するかを定量的に把握するための指標です。

重複コードを検出することで、同じ処理が複数箇所に実装されている可能性や、修正時に複数箇所の変更が必要になる可能性を確認できます。

以下の指標を提供します。

| 指標 | 説明 | 基本計測単位 |
|---|---|---|
| Duplication Rate | 重複しているコード行が全体に占める割合 | Project |

重複の検出は、同一ファイル内および異なるファイル間を対象とします。

計測単位や集計に関する共通ルールは[Metrics](./README.md)を参照してください。

## Duplication Rate

### Definition

Duplication Rateは、解析対象のソースコード全体に対して、重複しているコード行が占める割合を表す指標です。

本仕様では、Pythonのソースコードを字句単位で比較し、一定以上の長さで連続して一致するコードを重複として検出します。

計算式は以下のとおりです。

```text
Duplication Rate = Duplicated SLOC / Total SLOC × 100
```

各要素の意味は以下のとおりです。

| 要素 | 説明 |
|---|---|
| Duplicated SLOC | 重複範囲に含まれるコード行数 |
| Total SLOC | 解析対象全体のSLOC |
| Duplication Rate | 重複しているコード行の割合（%） |

SLOCの定義は[Size Metrics — SLOC](./size.md#sloc)に従います。

### Measurement Rules

#### Detection Method

重複の判定には、字句レベルの一致を使用します。

ソースコードをPythonのトークンとして比較し、連続したトークン列が一致する範囲を検出します。

比較における取り扱いは以下のとおりです。

| 対象 | 取り扱い |
|---|---|
| 空白・インデント幅 | 文字数の違いを無視する |
| 空行 | 無視する |
| コメント | 無視する |
| 改行 | 書式上の違いは無視する |
| 識別子・変数名 | 名前が異なれば一致しない |
| 数値・文字列リテラル | 字句表現が異なれば一致しない |
| 演算子・区切り記号 | 一致を必要とする |
| `INDENT` / `DEDENT` | ブロック構造を表すトークンとして比較する |

コメントや空白の違いによって、同じコードが別のコードとして判定されないようにします。

一方、識別子やリテラルの違いは正規化しません。

例えば、次の2つのコードは識別子が異なるため、同一のトークン列として扱いません。

```python
def calculate_price(price):
    return price * 2
```

```python
def calculate_cost(cost):
    return cost * 2
```

意味的に同じ処理であっても、字句レベルで一致しなければ重複と判定しません。

#### Minimum Match Length

重複と判定するための最小一致長は、**50トークン**とします。

- 50トークン以上連続して一致する場合、重複として検出します。
- 49トークン以下の一致は検出対象外とします。
- 比較から除外する空白・コメント・改行は、トークン数に含めません。
- 一致長は、重複する各出現箇所で同じトークン列を基準に判定します。

一致範囲に含まれるコードの物理行数は、重複判定の閾値には使用しません。

#### Detection Scope

重複の検出範囲は、解析対象全体とします。

以下の両方を検出します。

- 同一ファイル内の異なる位置に存在する重複
- 異なるファイル間に存在する重複

重複と判定するには、異なる2つ以上の出現箇所が必要です。

同じ出現箇所を自分自身と比較した結果は、重複として扱いません。

解析対象から除外されたファイルは、重複の検出対象にも含めません。

解析対象の選択規則については[Targets](../targets.md)を参照してください。

#### Duplicated SLOC

重複として検出されたトークン範囲を、ソースコードの行に対応付けてDuplicated SLOCを算出します。

- 重複範囲に含まれるSLOC対象行を計数します。
- 1行の一部だけが重複範囲に含まれる場合も、その行を1行として計数します。
- 空行・コメントのみの行は計数しません。
- 同じ行が複数の重複範囲に含まれても、1回だけ計数します。
- 同じトークン列が3箇所以上に出現する場合、各出現箇所のコード行を計数します。
- ファイルをまたいで重複している場合も、各ファイルの該当行を計数します。

重複行数は、検出した重複範囲の行数を単純に加算するのではなく、**重複に関係するSLOC対象行の集合**から算出します。

#### Calculation

Duplication Rateは、重複しているSLOCを解析対象全体のSLOCで除して算出します。

例えば、解析対象全体が100 SLOCで、そのうち20 SLOCが重複している場合、計測結果は以下となります。

```text
Duplicated SLOC = 20
Total SLOC      = 100

Duplication Rate = 20 / 100 × 100
                 = 20%
```

重複が検出されなかった場合は、Duplication Rateを0%とします。

Total SLOCが0の場合は、割合を算出できないため`null`とします。

### Boundary Cases

| ケース | 期待される動作 |
|---|---|
| 一致するトークン列が存在しない | `0%` |
| 49トークンの一致 | 重複と判定しない |
| 50トークンの一致 | 重複と判定する |
| 51トークン以上の一致 | 重複と判定する |
| 空白やコメントのみが異なる | 一致として扱う |
| 識別子が異なる | 異なるトークンとして扱う |
| リテラルが異なる | 異なるトークンとして扱う |
| 同一ファイル内の重複 | 検出する |
| 異なるファイル間の重複 | 検出する |
| 同じ位置との自己比較 | 重複と判定しない |
| 同じコードが3箇所以上に存在 | 各出現箇所を計数する |
| 重複範囲が重なる | 同じ行を二重計上しない |
| 1行の一部が重複 | その行を1行として計数する |
| コメントのみの行が重複範囲に含まれる | Duplicated SLOCには含めない |
| Total SLOCが0 | `null`と理由を返す |
| 解析対象ファイルが0件 | `null`と理由を返す |
| 解析可能なファイルが1件 | ファイル内の重複を検出する |

### Examples

#### Example 1: ファイル間の重複

以下の2つのファイルに、それぞれ50トークン以上の一致するコードが存在するとします。

```text
project/
├── module_a.py
└── module_b.py
```

両方のファイルで同じ10 SLOCが重複として検出され、ほかに重複がない場合、計測結果は次のようになります。

| ファイル | SLOC | Duplicated SLOC |
|---|---:|---:|
| module_a.py | 50 | 10 |
| module_b.py | 50 | 10 |
| 合計 | 100 | 20 |

```text
Duplication Rate = 20 / 100 × 100
                 = 20%
```

重複元と重複先を区別せず、両方の出現箇所を計数します。

#### Example 2: 重複範囲の重なり

100 SLOCのファイル内に、次の重複範囲が検出されたとします。

```text
重複範囲A：10〜30行目
重複範囲B：20〜40行目
```

各範囲は50トークン以上の一致条件を満たし、該当する31行はすべてSLOC対象行とします。

20〜30行目は両方の範囲に含まれていますが、二重には計数しません。

```text
Duplicated SLOC = 31
Total SLOC      = 100

Duplication Rate = 31%
```

#### Example 3: 3箇所以上の重複

同じトークン列が、互いに異なる3箇所に存在するとします。

```text
module_a.py：10行
module_b.py：10行
module_c.py：10行
```

各出現箇所が50トークン以上の一致条件を満たす場合、重複行数は合計30 SLOCです。

最初の出現箇所も重複しているコードの一部として計数します。

### Aggregation

Duplication Rateは、解析対象全体のSLOCとDuplicated SLOCから算出します。

ファイル単位では、以下の値を提供します。

| 指標 | 説明 |
|---|---|
| SLOC | ファイルのコード行数 |
| Duplicated SLOC | ファイル内で重複と判定されたコード行数 |
| Duplication Rate | ファイルのDuplicated SLOCをSLOCで除した割合 |

ファイル単位のDuplication Rateには、ほかの解析対象ファイルとの重複も反映します。

Project単位のDuplication Rateは、ファイル単位の重複率を単純平均せず、対象全体の行数から再計算します。

```text
Project Duplication Rate
  = Sum(Duplicated SLOC) / Sum(SLOC) × 100
```

計測不能な場合の共通ルールは[Metrics — Empty and Unavailable Results](./README.md#empty-and-unavailable-results)に従います。

### Partial Analysis

解析対象の一部のファイルで構文エラーや読み取りエラーが発生した場合は、正常に解析できたファイルのみを使用して重複を検出します。

- 解析に失敗したファイルは比較対象に含めません。
- Total SLOCには正常に解析できたファイルのSLOCのみを含めます。
- 解析結果が部分的であることを明示します。
- 正常に解析できたファイルのTotal SLOCも0の場合、Duplication Rateは`null`とします。

### Limitations

- Duplication Rateは字句レベルの一致を評価する指標であり、処理の意味的な等価性を判定するものではありません。
- 識別子やリテラルが異なる場合、同じ処理構造であっても検出されないことがあります。
- 50トークン未満の重複は検出対象外です。
- 文字列リテラルやdocstringも字句比較の対象となりますが、Duplicated SLOCはSLOCの定義に従って算出します。
- 重複が検出されたことだけで、不適切な実装であるとは判断できません。意図的に共通化しない方が適切なケースもあります。
- 解析対象のファイル構成や除外設定によって、Duplication Rateは変化します。

## References

- [Metrics — Overview](./README.md)
- [PMD — Finding Duplicated Code with CPD](https://pmd.github.io/pmd/pmd_userdocs_cpd.html)
- [SonarQube — Metrics Definitions](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition)
- [Python — Lexical Analysis](https://docs.python.org/3/reference/lexical_analysis.html)
- [Python — tokenize](https://docs.python.org/3/library/tokenize.html)