# 開発者向けドキュメント

Python 3.14以上とuvを使用します。

```bash
uv sync --locked
uv run pre-commit install
```

コミット時にRuffによるlintの安全な自動修正・整形と、Pyrightによるプロジェクト全体の型チェックを実行します。
フックはPythonファイルが対象の場合に実行されます。

手動でのチェックと修正:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pre-commit run --all-files

uv run ruff check --fix .
uv run ruff format .
```

Ruffは全安定ルールを基準に、整形と衝突するルールと著作権表記の強制を除外しています。
docstringはGoogle形式、行長は88文字、循環的複雑度の上限は8です。
テストではdocstringと`assert`の制限のみ緩和しています。
Pyrightはstrictに加え、未使用の戻り値、初期化されていない属性、暗黙のoverride、循環importなどもエラーにします。
型エラーの抑制が必要な場合は、対象ルールを指定した`# pyright: ignore[ルール名]`を使います。
Pythonファイルがまだない状態では、Pyright単体の実行は解析対象なしで終了します。
