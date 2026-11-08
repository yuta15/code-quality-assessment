# Code Analysis — Output

## Overview

Code Analysisでは、ソースコードの計測結果および比較結果を、用途に応じた形式で出力できます。

解析結果をターミナルで確認するほか、JSONやMarkdownとして保存し、CI/CDでの利用やレポート作成などに活用できます。

出力形式によって表示方法は異なりますが、元となる計測値や比較結果の意味は変わりません。

## Supported Formats

以下の出力形式に対応します。

| Format | 用途 | 特徴 |
|---|---|---|
| Console | ターミナルでの確認 | 人が読みやすい形式で結果を表示する |
| JSON | ツール間連携・結果の保存 | 機械可読な構造化データを提供する |
| Markdown | ドキュメント・レポート | 表形式で結果を確認・共有できる |

デフォルトの出力形式はConsoleとします。

CLIでは`--format`オプションで出力形式を指定できます。

```bash
cqa analyze ./src
cqa analyze ./src --format json
cqa analyze ./src --format markdown

cqa compare ./before ./after --format json
```

Python APIでは、計測結果や比較結果を構造化されたPythonデータとして取得できます。

## Output Content

出力内容は、AnalysisとComparisonで異なります。

### Analysis Result

計測結果には、以下の情報を含めます。

| 項目 | 内容 |
|---|---|
| Analysis Scope | 指定された解析対象の情報 |
| Metrics | 各指標の計測値と集計値 |
| Details | 関数・クラス・ファイル単位の計測結果 |
| Errors | 解析中に発生したエラー |
| Unresolved | 静的解析で特定できなかった情報 |
| Metadata | 計測モデル・バージョン・設定など |
| Status | 解析結果の完全性を示す状態 |

各指標の定義と集計方法は[Metrics](./metrics/README.md)に従います。

### Comparison Result

比較結果には、以下の情報を含めます。

| 項目 | 内容 |
|---|---|
| Before | 比較元の解析結果 |
| After | 比較先の解析結果 |
| Differences | 比較可能な計測値の差分と変化率 |
| Incompatible Metrics | 比較できなかった指標とその理由 |
| Metadata | 比較時の計測条件など |
| Status | 比較結果の完全性を示す状態 |

差分の計算方法と比較条件は[Comparison](./comparison.md)に従います。

## Result Status

解析結果には、結果の完全性を示す状態を付与します。

| Status | 説明 |
|---|---|
| `complete` | 対象となるファイルの解析がすべて正常に完了した |
| `partial` | 一部のファイルで解析に失敗し、正常に解析できた範囲の結果を保持している |

解析対象ファイルが0件の場合は、正常な解析結果として`complete`を返します。

静的に特定できない依存関係が存在していても、ファイルの解析自体が完了している場合は`complete`とします。ただし、未解決情報は別途保持し、該当する指標が不完全であることを確認できるようにします。

計測不能な指標については、`null`とその理由を保持します。

比較結果では、BeforeまたはAfterに`partial`が含まれる場合、比較結果も`partial`とします。

## JSON

JSONは、解析結果を機械可読な形式で表現するための出力形式です。

計測値だけでなく、解析対象、詳細結果、計測条件、エラー、未解決情報を保持します。

### General Rules

- UTF-8で出力します。
- JSONとして有効な構造を出力します。
- 数値はJSONの数値として表現します。
- 計測不能な値は`null`として表現します。
- 計測不能の理由を別途保持します。
- パーセント値は`%`記号を付けず、0〜100の数値で表現します。
- 計測対象が存在しない場合は、共通仕様に従って0または`null`を返します。
- ファイル・関数・クラスの詳細結果を保持します。
- エラーや未解決情報を保持します。
- JSONの構造を識別するスキーマバージョンを含めます。

出力順序に依存しない利用ができるよう、各指標は識別子によって区別します。

### Analysis Example

以下は、計測結果の一部を示した例です。

```json
{
  "schema_version": "1",
  "type": "analysis",
  "status": "complete",
  "scope": {
    "path": "./src",
    "file_count": 2
  },
  "metrics": {
    "sloc": {
      "total": 120
    },
    "function_count": {
      "total": 8
    },
    "cyclomatic_complexity": {
      "total": 20,
      "average": 2.5,
      "maximum": 6
    },
    "duplication_rate": {
      "value": 10.0
    }
  },
  "details": {
    "files": []
  },
  "errors": [],
  "unresolved": [],
  "metadata": {
    "tool_version": "1.0.0",
    "measurement_models": {},
    "settings": {}
  }
}
```

この例では、`metrics`にAnalysis Scope全体の集計値を格納しています。

`details`には、各ファイルおよびその内部の関数・クラスについて、取得可能な計測結果を格納します。

各計測値は指標の識別子と集計方法によって識別できるものとします。

`details.files`の空配列は例示のための省略です。実際の出力では、解析できたファイルの詳細結果を含めます。

### Unavailable Metric Example

計測対象が存在しないため平均値を算出できない場合は、値と理由を区別します。

```json
{
  "lcom4": {
    "average": null,
    "maximum": null,
    "unavailable_reason": "NO_MEASURABLE_CLASSES"
  }
}
```

エラーや未解決の依存関係が存在する場合も、該当する情報を計測結果から識別できるものとします。

### Comparison Example

以下は比較結果の一部です。

```json
{
  "schema_version": "1",
  "type": "comparison",
  "status": "complete",
  "before": {
    "scope": "./before",
    "metrics": {
      "sloc": {
        "total": 200
      }
    }
  },
  "after": {
    "scope": "./after",
    "metrics": {
      "sloc": {
        "total": 180
      }
    }
  },
  "differences": {
    "sloc": {
      "total": {
        "before": 200,
        "after": 180,
        "difference": -20,
        "change_rate": -10.0
      }
    }
  },
  "incompatible_metrics": [],
  "metadata": {}
}
```

`differences`には、比較可能な計測値についてBefore・After・Difference・Change Rateを含めます。

比較不能な指標については、差分を算出せず、理由を保持します。

BeforeとAfterの解析結果については、保存済み結果として必要な計測条件やエラー情報も保持できるものとします。

### Schema Compatibility

JSONの構造にはスキーマバージョンを付与します。

- 同じスキーマバージョンでは、既存フィールドの意味を変更しません。
- 新しい指標が追加された場合は、新しい指標の識別子で表現します。
- 計測指標が追加されても、既存指標の識別子や意味を変更しません。
- 互換性のないJSON構造の変更では、スキーマバージョンを更新します。
- 保存済み解析結果を読み込む際は、対応可能なスキーマバージョンであることを確認します。

保存済み解析結果の比較では、JSONスキーマの互換性と計測モデルの互換性を別々に確認します。

## Markdown

Markdownは、解析結果を人が読みやすい表形式で共有するための出力形式です。

### General Rules

- UTF-8のMarkdownテキストとして出力します。
- 計測対象と解析状態を明示します。
- 集計値を表形式で表示します。
- 計測不能な値は`N/A`と表示し、理由を確認できるようにします。
- 解析エラーや未解決情報が存在する場合は、その内容を表示します。
- 各指標の意味や集計方法はJSONと同じものを使用します。

### Analysis Example

```markdown
# Code Analysis Report

## Summary

- Target: ./src
- Status: complete
- Files: 2

## Metrics

| Metric | Total | Average | Maximum |
|---|---:|---:|---:|
| SLOC | 120 | — | — |
| Function Count | 8 | — | — |
| Cyclomatic Complexity | 20 | 2.5 | 6 |
| Duplication Rate | 10% | — | — |

## Errors

None
```

関数・クラス・ファイル単位の詳細結果も、必要な情報を確認できる形で出力します。

### Comparison Example

```markdown
# Code Comparison Report

## Summary

- Before: ./before
- After: ./after
- Status: complete

## Differences

| Metric | Before | After | Difference | Change Rate |
|---|---:|---:|---:|---:|
| SLOC | 200 | 180 | -20 | -10% |
| Cyclomatic Complexity (Average) | 5 | 3 | -2 | -40% |
| Duplication Rate | 15% | 10% | -5pt | -33.33% |
```

比較不能な指標や部分的な解析結果が存在する場合は、結果の解釈に必要な注意事項を表示します。

## Console

Consoleは、ターミナル上で解析結果を確認するための出力形式です。

### General Rules

- 計測対象と解析状態を表示します。
- 集計値を読みやすい形式で表示します。
- 計測不能な値は`N/A`と表示します。
- エラーや未解決情報が存在する場合は、それらを確認できるようにします。
- 出力先がカラー表示に対応していなくても、情報を読み取れる形式とします。
- 表示形式が変わっても、計測値の意味は変えません。

### Example

```text
Code Analysis
Target: ./src
Status: complete
Files: 2

Metrics
-------------------------------------------
SLOC                         120
Function Count                 8
Cyclomatic Complexity
  Total                       20
  Average                    2.5
  Maximum                      6
Duplication Rate             10%

Errors: 0
```

Consoleのレイアウト、罫線、色などの表示方法は、計測規則には影響しません。

## Numerical Formatting

JSONでは、計測値と差分の数値を表示用に丸めず保持します。

MarkdownとConsoleでは、読みやすさのために表示上の丸めを行います。

- 整数値は整数として表示します。
- 小数値は小数点以下2桁まで表示します。
- 端数処理は四捨五入とします。
- パーセント値には`%`を付けます。
- パーセントポイントによる差分には`pt`を付けます。
- 計測不能な値は`N/A`と表示します。
- 表示上の丸めは元の計測値や比較計算に影響しません。

例えば、変化率が`-33.333...%`の場合、MarkdownとConsoleでは`-33.33%`と表示します。

## Output Destination

CLIでは、出力先を指定できます。

出力先を指定しない場合は、標準出力に結果を表示します。

```bash
cqa analyze ./src --format json --output result.json
cqa analyze ./src --format markdown --output report.md
cqa compare ./before ./after --format json --output comparison.json
```

`--output`を指定した場合は、指定先に出力結果を保存します。

### Output Rules

- 指定された出力形式に従って保存します。
- 保存先のディレクトリが存在しない場合は、エラーとします。
- ファイルへ書き込めない場合は、エラーとします。
- 既存ファイルが存在する場合は上書きします。
- 出力ファイルの拡張子だけで出力形式を変更しません。
- 出力形式は`--format`の指定を優先します。
- `--output`を省略した場合は標準出力へ出力します。

## Error Output

解析対象の指定、ファイル解析、比較、出力処理でエラーが発生した場合は、原因を確認できる情報を提供します。

### Fatal Errors

解析を継続できないエラーが発生した場合は、エラー内容を出力し、非ゼロの終了コードを返します。

例：

```text
Error: TARGET_NOT_FOUND
Path: ./missing
Message: Target path does not exist.
```

### Partial Failures

一部のファイルで解析に失敗した場合も、正常に解析できた範囲の結果を出力します。

- 正常に解析できたファイルの計測結果を保持します。
- 失敗したファイルのパスとエラー情報を含めます。
- 解析状態を`partial`とします。
- CLIでは非ゼロの終了コードを返します。

JSONを標準出力へ出力する場合、JSON以外の診断メッセージを同じ標準出力へ混在させません。

CLIの診断メッセージは標準エラー出力に出力します。

エラー処理の詳細は[Targets — Error Handling](./targets.md#error-handling)を参照してください。

## Empty Results

解析対象が0件の場合も、正常な解析結果として出力します。

- 計測対象ファイル数を0とします。
- 計数・合計指標は0とします。
- 計測対象がない平均値・最大値は`null`とします。
- Duplication Rateは分母が0のため`null`とします。
- 計測不能な値には理由を保持します。
- CLIでは正常終了とします。

比較可能な指標が0件の場合も、[Comparison](./comparison.md#no-comparable-metrics)の規則に従って空の比較結果を出力します。

## Extensibility

出力形式は、計測処理や比較処理から独立して扱います。

- 新しい出力形式を追加しても、既存の計測規則は変更しません。
- 新しいメトリクスを追加しても、既存の出力形式で計測結果を表現できることを基本とします。
- 出力形式ごとの表示方法は、それぞれの形式に応じて定義します。
- 計測結果や比較結果の意味は、出力形式に依存させません。

ただし、将来的に既存のデータ構造では表現できない情報が追加された場合は、JSONスキーマの互換性を考慮して拡張します。

## Limitations

- MarkdownとConsoleは人間による確認を目的とした形式であり、保存済み解析結果の再入力には使用しません。
- JSONは機械可読性と再利用を目的とするため、表示上のレイアウトは保証しません。
- 表示上の丸めにより、MarkdownやConsoleの数値から差分を再計算すると、内部の計算結果と一致しない場合があります。
- ファイル単位・関数単位などの詳細な計測結果は出力できますが、ComparisonではAnalysis Scope単位の集計値を比較します。
- 出力形式によって表示方法は異なりますが、計測結果そのものの意味は変わりません。

## Related Documents

- [Code Analysis](./README.md)
- [Usage](./usage.md)
- [Targets](./targets.md)
- [Metrics](./metrics/README.md)
- [Comparison](./comparison.md)