# Usage

## Overview

Code Analysis は、CLIまたはPython APIから利用できます。

いずれのインターフェースでも、ソースコードの計測と、複数の計測結果の比較を行えます。

## CLI

CLIでは、コマンドから解析対象や出力形式を指定して実行します。

### Code Analysis

指定したソースコードを解析し、計測結果を取得します。

```bash
cqa analyze ./src
```

### Comparison

2つのソースコードを解析し、計測結果を比較します。

```bash
cqa compare ./before ./after
```

### Output

出力形式はオプションで指定できます。

```bash
cqa analyze ./src --format json
cqa compare ./before ./after --format markdown
```

指定可能な形式や出力内容については、[出力形式](output.md)を参照してください。

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

比較結果には、各指標の差分や変化率などが含まれます。

## Notes

- CLIとPython APIでは、同じ解析条件に対して同じ計測結果が得られます。
- 解析対象にはファイルまたはディレクトリを指定できます。
- 対応言語や対象ファイルの選択規則は[解析対象](targets.md)を参照してください。
- 計測できる指標は[計測指標](metrics.md)を参照してください。
- 比較の詳細は[比較方法](comparison.md)を参照してください。

> 現在開発中です。記載したコマンドおよびAPIは予定しているインターフェースであり、今後変更される可能性があります。