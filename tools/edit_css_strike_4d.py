# -*- coding: utf-8 -*-
"""
工事4d-A: 過去の清算の送金行で、打ち消し線が「✓ 名前 日時」（.transfer-by）まで伸びる問題の CSS 側。

  ・line-through を .transfer-row.done .transfer-pair だけに付ける
    （灰色 --gray-500 は .transfer-names 全体のまま）
  ・効いていなかった .transfer-row.done .transfer-by { text-decoration: none; } を削除する

DOM 側の変更は tools/edit_ui_strike_4d.py。PC・スマホ共通。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_strike_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

EDITS = [
("""
.transfer-row.done .transfer-names { text-decoration: line-through; color: var(--gray-500); }
""",
"""
.transfer-row.done .transfer-names { color: var(--gray-500); }
/* 工事4d: 線は「A → B」だけ。祖先に付けた線は子の .transfer-by にも引かれて消せないため */
.transfer-row.done .transfer-pair { text-decoration: line-through; }
"""),
("""
.transfer-row.done .transfer-by { text-decoration: none; }
""",
"""
"""),
]


def apply(path, edits, marker):
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if marker in src:
        print("すでに適用済みです。何もしません: " + path)
        return 0
    errors = []
    for before, _ in edits:
        n = src.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    out = src
    for before, after in edits:
        out = out.replace(fix(before), fix(after), 1)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + path)
    return 0


if __name__ == "__main__":
    sys.exit(apply(TARGET, EDITS, ".transfer-row.done .transfer-pair"))
