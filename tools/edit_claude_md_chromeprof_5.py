# -*- coding: utf-8 -*-
"""
工事5-0: CLAUDE.md の「テスト」の節に、ヘッドレス Chrome のプロファイルの決めごとを 1 行足す。

経緯: 工事4d で、同じプロファイルで起動したヘッドレス Chrome が
py -m http.server から配った古い js をキャッシュし、変更前の画面を確認してしまった。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_claude_md_chromeprof_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "CLAUDE.md")

BEFORE = """- 直したバグは再現テストを追加してから直す
"""
AFTER = """- 直したバグは再現テストを追加してから直す
- 画面の通し確認（ヘッドレス Chrome）は毎回新しい一時フォルダを --user-data-dir に指定して起動する（同じプロファイルだと http.server から配った古い js がキャッシュされる）
"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "--user-data-dir" in src:
        print("すでに適用済みです。何もしません。")
        return 0
    n = src.count(fix(BEFORE))
    if n != 1:
        print("中止しました（置換対象の一致が %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    out = src.replace(fix(BEFORE), fix(AFTER), 1)
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
