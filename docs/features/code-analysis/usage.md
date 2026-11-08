# Usage

## Overview

Code Analysis は、CLIまたはPython APIから利用できます。

いずれのインターフェースでも、ソースコードの計測と、2つの解析結果の比較を行えます。比較対象にはソースコードおよび保存済みのJSON解析結果を使用できます。

## CLI

CLIでは、コマンドから解析対象や出力形式を指定して実行します。

### Code Analysis

指定したソースコードを解析し、計測結果を取得します。

```bash
cqa analyze ./src
```

### Comparison

2つのソースコードを解析し、Analysis Scope（指定した解析対象全体）の集計値を比較します。ファイル・関数・クラスの対応付けは行いません。保存済みのJSON解析結果も比較対象にできます。

 ```bash
cqa compare ./before ./after
cqa compare --before-result ./before.json --after-result ./after.json
cqa compare ./after --before-result ./before.json
cqa compare ./before --after-result ./after.json
```

`--before-result`と`--after-result`はそれぞれ保存済みのAnalysis Result（JSON）を指定します。各側にはソースコードの位置引数か保存済みJSON入力のどちらか一方を指定し、拡張子から入力種別を推測しません。重複指定と入力不足はエラーとします。

### Output

出力形式は`--format`オプションで指定できます。デフォルトはConsoleです。`--output`を指定するとファイルに保存し、省略すると標準出力へ出力します。

```bash
cqa analyze ./src --format json
cqa compare ./before ./after --format markdown
cqa analyze ./src --format json --output result.json
cqa compare ./before ./after --format json --output comparison.json
```

Console・JSON・Markdownの出力規則、既存ファイルの上書き、エラー時の出力については[出力形式](output.md)を参照してください。保存済み結果のJSONスキーマも同ドキュメントで定義します。

## Python API

Pythonプログラムから解析機能を直接利用できます。

### Code Analysis

```python
from cqa import analyze

result = analyze("./src")
```

解析結果は、Pythonプログラムから各計測値を参照できる構造化データとして取得します。

### Comparison

```python
from cqa import analyze, compare

before = analyze("./before")
after = analyze("./after")

result = compare(before, after)
```

比較結果には、Analysis Scope全体の集計指標についての差分や変化率などが含まれます。`compare`には保存済みJSONからAnalysis Resultとして復元・検証したデータも渡せます。復元時には計測値・計測条件・未解決情報を保持します。

## Notes

- CLIとPython APIでは、同じ解析条件に対して同じ計測結果が得られます。
- 解析対象にはファイルまたはディレクトリを指定できます。
- 対応言語や対象ファイルの選択規則は[解析対象](targets.md)を参照してください。
- 計測できる指標は[計測指標](metrics/README.md)を参照してください。
- 比較の詳細は[比較方法](comparison.md)を参照してください。
- 解析結果または比較結果が`partial`の場合、CLIは結果を出力したうえで非ゼロ終了します。比較可能な指標が0件でも双方が`complete`なら正常終了します。
