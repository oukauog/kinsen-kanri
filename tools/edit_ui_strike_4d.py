# -*- coding: utf-8 -*-
"""
工事4d-A: 過去の清算の送金行で、打ち消し線が「✓ 名前 日時」（.transfer-by）まで伸びる問題の DOM 側。

「A → B」の文字を <span class="transfer-pair">…</span> で包み、
.transfer-by はその外側（.transfer-names の直下、.transfer-pair の後ろ）に置く。
CSS 側で line-through を .transfer-pair だけに付ける（tools/edit_css_strike_4d.py）。

背景: 祖先に付いた text-decoration は同じ行内の子孫にも引かれ、
子に text-decoration: none を書いても消せない（CSS の仕様）。
線を付ける要素の外に .transfer-by を出すしかない。

「清算を確定する」側（draft の送金一覧）は .settlement-* のクラスで別物なので触らない。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_strike_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

EDITS = [(
"""              '<span class="transfer-names">' + esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + mark + '</span>' +""",
"""              // 打ち消し線は「A → B」（.transfer-pair）だけに付ける。印（.transfer-by）はその外に置く
              '<span class="transfer-names"><span class="transfer-pair">' +
              esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + '</span>' + mark + '</span>' +""",
)]


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
    sys.exit(apply(TARGET, EDITS, 'class="transfer-pair"'))
