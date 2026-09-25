# -*- coding: utf-8 -*-
"""
工事6-A: docs/10_仕様書_v2再設計.md の §5.2 の 1 つ目の箇条書きを、工事5 の並び順に合わせて直す。

  修正前: `users/{uid}/groups` に登録されたグループを名前で一覧。リアルタイム更新
  修正後: 自分で決めた並び順（§3 の order。無ければ joinedAt 順）で一覧 … リアルタイム更新

§3 は変えない。
置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_spec_sidebar_6.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "docs", "10_仕様書_v2再設計.md")

BEFORE = """- `users/{uid}/groups` に登録されたグループを名前で一覧。リアルタイム更新
"""
AFTER = """- `users/{uid}/groups` に登録されたグループを、自分で決めた並び順（§3 の order。無ければ joinedAt 順）で一覧。新しく作った・参加したグループは一番下に入る。各行の右端のつまみ（⋮⋮）をドラッグして並べ替えられ、その順は自分のアカウントだけに保存される（他のメンバーには影響しない）。リアルタイム更新
"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if fix(AFTER) in src:
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
