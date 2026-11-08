# CLI Reference

Code Analysisが提供するコマンドラインインターフェースの仕様を定義します。

CLIは`cqa`コマンドから利用できます。

## Commands

| Command | Description |
|---|---|
| `cqa analyze` | Pythonソースコードを解析する |
| `cqa compare` | 2つの解析結果を比較する |

## `cqa analyze`

指定したPythonファイルまたはディレクトリを解析し、計測結果を出力します。

### Synopsis

```text
cqa analyze <target> [--exclude <pattern> ...]
                     [--use-gitignore]
                     [--format <format>]
                     [--output <path>]
```

### Arguments

| Name | Required | Description |
|---|---|---|
| `target` | Yes | 解析対象のPythonファイルまたはディレクトリ |

`target`には相対パスまたは絶対パスを指定できます。

ディレクトリを指定した場合は、配下のPythonファイルを再帰的に探索します。

### Options

| Option | Value | Default | Description |
|---|---|---|---|
| `--exclude` | Globパターン | なし | 指定したファイル・ディレクトリを除外する |
| `--use-gitignore` | フラグ | 無効 | `.gitignore`の除外規則を適用する |
| `--format` | `console`, `json`, `markdown` | `console` | 出力形式を指定する |
| `--output` | ファイルパス | なし | 結果の保存先を指定する |

`--exclude`は複数回指定できます。複数のパターンのいずれかに一致する対象を除外します。

`--use-gitignore`を指定した場合も、`--exclude`による除外は適用されます。

解析対象の選択・除外規則は[Targets](./targets.md)に従います。

### Examples

単一ファイルを解析します。

```bash
cqa analyze ./src/main.py
```

ディレクトリを解析します。

```bash
cqa analyze ./src
```

特定のファイル・ディレクトリを除外します。

```bash
cqa analyze ./src \
  --exclude "**/generated/*.py" \
  --exclude "**/test_*.py"
```

Git ignoreの規則を適用します。

```bash
cqa analyze . --use-gitignore
```

計測結果をJSON形式で保存します。

```bash
cqa analyze ./src --format json --output analysis.json
```

### Exit Status

| Condition | Status |
|---|---|
| すべての対象ファイルの解析に成功 | `0` |
| 解析対象が0件 | `0` |
| 一部のファイルの解析に失敗 | 非ゼロ |
| 解析対象の指定に致命的なエラーがある | 非ゼロ |
| 結果の出力に失敗 | 非ゼロ |

一部のファイルで解析に失敗した場合も、成功したファイルの計測結果とエラー情報を出力します。

未解決依存の存在のみを理由として非ゼロ終了にはしません。

## `cqa compare`

2つのAnalysis Resultを比較し、指標ごとの差分と変化率を出力します。

比較対象には、Pythonソースコードまたは保存済みAnalysis Result JSONを使用できます。

### Synopsis

```text
cqa compare [<before>] [<after>]
            [--before-result <path>]
            [--after-result <path>]
            [--exclude <pattern> ...]
            [--use-gitignore]
            [--format <format>]
            [--output <path>]
```

### Arguments

| Name | Description |
|---|---|
| `before` | 比較元のPythonファイルまたはディレクトリ |
| `after` | 比較先のPythonファイルまたはディレクトリ |

各側には、ソースコードの位置引数または保存済みAnalysis Result JSONのいずれか一方を指定します。

### Input Options

| Option | Value | Description |
|---|---|---|
| `--before-result` | JSONファイルパス | Beforeに保存済みAnalysis Resultを指定する |
| `--after-result` | JSONファイルパス | Afterに保存済みAnalysis Resultを指定する |

#### Input Combinations

| Before | After | Positional Arguments | Result Options |
|---|---|---|---|
| ソースコード | ソースコード | 2 | なし |
| 保存済みJSON | ソースコード | 1（After） | `--before-result` |
| ソースコード | 保存済みJSON | 1（Before） | `--after-result` |
| 保存済みJSON | 保存済みJSON | 0 | 両方指定 |

位置引数が1つの場合、指定済みの結果オプションと反対側の入力として解釈します。

各側の入力は必ず1つとし、入力不足や重複指定をエラーとします。

保存済みJSONの入力種別は、`--before-result`または`--after-result`によって明示します。位置引数の拡張子からJSON入力と推測しません。

### Analysis Options

ソースコードを比較入力として指定する場合、解析対象の選択に次のオプションを使用できます。

| Option | Value | Default | Description |
|---|---|---|---|
| `--exclude` | Globパターン | なし | 解析対象から除外する |
| `--use-gitignore` | フラグ | 無効 | Git ignoreの除外規則を適用する |

`--exclude`は複数回指定できます。

解析オプションは、Before・Afterのうちソースコードとして指定された側に適用します。

両側がソースコードの場合は、同じ解析オプションをそれぞれの解析対象に適用します。Globの基準位置と`.gitignore`の解釈は、各解析対象について独立に評価します。

片側のみがソースコードの場合は、その側にのみ解析オプションを適用します。

保存済みJSONを指定した側には解析オプションを適用せず、保存されている計測結果と条件を使用します。

**Before・Afterの両側が保存済みJSONの場合、`--exclude`または`--use-gitignore`の指定は入力エラーとします。** 解析対象の選択が発生しないため、これらのオプションは使用できません。

### Output Options

| Option | Value | Default | Description |
|---|---|---|---|
| `--format` | `console`, `json`, `markdown` | `console` | 出力形式を指定する |
| `--output` | ファイルパス | なし | 比較結果の保存先を指定する |

### Examples

2つのディレクトリを比較します。

```bash
cqa compare ./before ./after
```

保存済みAnalysis Result同士を比較します。

```bash
cqa compare \
  --before-result ./before.json \
  --after-result ./after.json
```

保存済みのBeforeとソースコードのAfterを比較します。

```bash
cqa compare ./after \
  --before-result ./before.json
```

ソースコードのBeforeと保存済みのAfterを比較します。

```bash
cqa compare ./before \
  --after-result ./after.json
```

両側のソースコードに共通の除外条件を指定します。

```bash
cqa compare ./before ./after \
  --exclude "**/generated/*.py"
```

保存済みのBeforeとソースコードのAfterを比較し、Afterにだけ除外条件を適用します。

```bash
cqa compare ./after \
  --before-result ./before.json \
  --exclude "**/generated/*.py"
```

比較結果をMarkdown形式で保存します。

```bash
cqa compare ./before ./after \
  --format markdown \
  --output comparison.md
```

### Exit Status

| Condition | Status |
|---|---|
| 比較が正常に完了し、両側が`complete` | `0` |
| 比較可能な指標が0件で、両側が`complete` | `0` |
| BeforeまたはAfterが`partial` | 非ゼロ |
| 入力形式・入力指定が不正 | 非ゼロ |
| 結果の出力に失敗 | 非ゼロ |

一部の指標が互換性を持たない場合も、他の比較可能な指標について処理を継続します。

比較可能な指標が0件の場合は、空の比較結果と比較不能の理由を出力します。

比較規則は[Comparison](./comparison.md)に従います。

## Output

### Formats

| Format | Description |
|---|---|
| `console` | ターミナル向けの表示形式 |
| `json` | 機械可読なJSON |
| `markdown` | Markdownレポート |

`--format`を省略した場合は`console`を使用します。

出力形式はファイル拡張子によって自動的に変更されません。

### Output Destination

`--output`を省略した場合、結果を標準出力（stdout）に出力します。

`--output`を指定した場合、指定されたファイルへ結果を書き込み、**stdoutには何も出力しません。**

ファイル保存の成功を通知するメッセージもstdoutへ出力しません。診断が必要な場合はstderrを使用します。

既存ファイルが存在する場合は、出力の生成と書き込みが正常に完了したときのみ置換します。

出力に失敗した場合は、既存ファイルの内容を保持します。

### Standard Output and Standard Error

| Stream | Content |
|---|---|
| stdout | `--output`省略時の解析・比較結果 |
| stderr | 入力エラー、解析失敗、出力失敗などの診断情報 |

`--output`指定時は、正常終了・部分失敗・出力失敗のいずれの場合もstdoutを空とします。

JSONをstdoutへ出力する場合、診断メッセージや案内文をJSONに混在させません。

`partial`の結果も、有効なJSONとして出力します。

### Result Status

| Status | Description |
|---|---|
| `complete` | 対象ファイルの解析がすべて成功 |
| `partial` | 一部の対象ファイルで解析に失敗 |

解析対象0件の場合は`complete`です。

未解決依存が存在していても、ファイル解析自体がすべて成功していれば`complete`とします。

JSONスキーマ、数値表示、計測不能値、保存時の規則は[Output](./output.md)に従います。

## Error Handling

### Input Errors

| Condition | Error Code |
|---|---|
| 指定した解析対象が存在しない | `TARGET_NOT_FOUND` |
| 指定した解析対象にアクセスできない | `TARGET_ACCESS_DENIED` |
| 非対応ファイルを直接指定した | `UNSUPPORTED_FILE_TYPE` |

致命的な入力エラーでは処理を中断し、stderrへ診断を出力して非ゼロ終了します。

### File Analysis Errors

| Condition | Error Code |
|---|---|
| ソースコードの構文エラー | `SYNTAX_ERROR` |
| 個別ファイルの読み込み失敗 | `FILE_READ_ERROR` |

個別ファイルの解析失敗では、他の解析可能なファイルの処理を継続します。

結果には成功したファイルの計測値と、失敗したファイルのエラー情報を含めます。

結果の`status`は`partial`とし、結果出力後に非ゼロ終了します。

### Invalid Command Arguments

以下を不正なコマンド指定として扱います。

- 存在しないサブコマンド
- 未知のオプション
- 必須の位置引数またはオプション値の不足
- 許可されていない余剰の位置引数
- `--format`に対応していない値
- `compare`で同一側への入力を重複指定した場合
- `compare`でBefore・Afterの入力が不足している場合
- `compare`の両側を保存済みJSONで指定し、`--exclude`または`--use-gitignore`を併用した場合

不正なコマンド指定では、stderrへ診断を出力して非ゼロ終了します。

診断文言の完全一致や、具体的な非ゼロ終了コードは公開契約としません。

## Related Documents

- [Code Analysis](./README.md)
- [Usage](./usage.md)
- [Python API](./python-api.md)
- [Targets](./targets.md)
- [Metrics](./metrics/README.md)
- [Comparison](./comparison.md)
- [Output](./output.md)