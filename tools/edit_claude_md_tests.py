# -*- coding: utf-8 -*-
"""
工事2: CLAUDE.md の「テスト」の節を、テスト一括実行（node tests/run_all.js）に差し替える。

理由: テストファイルが calc / authdomain / migrate の 3 本になり、
「node tests/calc.test.js だけ通せばよい」という書き方だと取りこぼす。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_claude_md_tests.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "CLAUDE.md")

BEFORE = """## テスト（C-1 / C-2）
- 純粋ロジック（按分・残高・清算）は `js/calc.js` に置き、`tests/calc.test.js` を `node tests/calc.test.js` で全通過させる
- ロジックに触る前に、現状の挙動を固定するテストを先に書く
- 直したバグは再現テストを追加してから直す"""

AFTER = """## テスト（C-1 / C-2）
- テストは `node tests/run_all.js` で一括実行し、全通過させる（`tests/*.test.js` を自動で拾う）
- 純粋ロジックは DOM・Firebase に依存しない形で `js/` に置く（按分・残高・清算は `js/calc.js`、旧データの変換は `js/migrate.js`）。新しいテストは `tests/<名前>.test.js` として足せば `run_all` が拾う
- ロジックに触る前に、現状の挙動を固定するテストを先に書く
- 直したバグは再現テストを追加してから直す"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    if "run_all.js" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: CLAUDE.md のテストの節を差し替えました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
