# -*- coding: utf-8 -*-
"""
工事5: docs/10_仕様書_v2再設計.md の §3 データモデルに、サイドバーの並び順（order）を足す。

  ・users/{uid}/groups/{code} を { joinedAt, order? } に直す
  ・§3 の箇条書きの後に、並び順の決めごとを 1 段落足す

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_spec_order_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "docs", "10_仕様書_v2再設計.md")

EDITS = [
("""  groups/{code}: { joinedAt }                 ← 左サイドバーの一覧の元
""",
"""  groups/{code}: { joinedAt, order? }         ← 左サイドバーの一覧の元（order は並び順、工事5）
"""),
("""- 金額は整数円。按分の端数は v1 と同じ（表示時に丸め、残高は浮動で持ち、清算時に四捨五入）
""",
"""- 金額は整数円。按分の端数は v1 と同じ（表示時に丸め、残高は浮動で持ち、清算時に四捨五入）

**サイドバーの並び順（工事5）**: 並び順は人ごとの好みなので `users/{uid}/groups/{code}/order`（数値）に持ち、`groups/{code}` 側には何も書かない（他のメンバーには影響しない）。表示順のキーは「`order` が数値なら `order`、無ければ `joinedAt`（それも無ければ 0）」の昇順で、同点はコードの文字列順（`order` が文字列や null のときは無いものとして扱う）。`order` の無い既存グループはバックフィルせず、並べるときだけ `joinedAt` を使う。新規作成とコード参加は `order` =「今の自分の一覧の表示順キーの最大 + 1」（空なら 0）で書くので必ず一番下に入る（旧データの移行で入るグループは `order` 無し＝`joinedAt` 順）。つまみのドラッグ＆ドロップで並びが確定したら、その表示順で全グループに `order` = 0, 1, 2, … を `users/{uid}/groups` への 1 回の update（キーは `<code>/order`）で書き、`joinedAt` には触れない。`users/{uid}` は本人しか読み書きしないので、セキュリティルール（§4）は変更しない。実装は `js/group_order.js`（`sortCodes` / `nextOrder` / `attach`、並べ替えは SortableJS）と `js/store.js` の `setGroupOrder`
"""),
]


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "サイドバーの並び順（工事5）" in src:
        print("すでに適用済みです。何もしません。")
        return 0
    errors = []
    out = src
    for before, after in EDITS:
        n = out.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
            continue
        out = out.replace(fix(before), fix(after), 1)
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
