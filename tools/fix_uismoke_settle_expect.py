# -*- coding: utf-8 -*-
"""
工事3: 通し確認の期待値の直し。

tools/edit_uismoke_settle.py で入れた 2 件の期待額が、実装ではなく
テスト側の計算間違いだった（画面の表示の方が正しい）。

  ・累計の残高: 3000 円（3 人）＋ 600 円（3 人）→ P は +2,400（+2,200 ではない）
  ・取り消し後の残高: 上記に 900 円（3 人）が加わる → P は +3,000（+2,300 ではない）

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/fix_uismoke_settle_expect.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

REPS = [
    ("累計の期待額を 2,400 に直す",
     """        check('累計に切り替えると清算済みも計算に入る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,200') >= 0,""",
     """        check('累計に切り替えると清算済みも計算に入る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,400') >= 0,"""),
    ("取り消し後の期待額を 3,000 に直す",
     """        check('取り消すと残高が元に戻る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,300') >= 0,""",
     """        check('取り消すと残高が元に戻る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥3,000') >= 0,"""),
]


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors, plan = [], []
    for label, before, after in REPS:
        b = fix(before)
        n = src.count(b)
        if n != 1:
            errors.append("%s: 一致 %d 件（1 件であるべき）" % (label, n))
        plan.append((label, b, fix(after)))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for label, b, a in plan:
        out = out.replace(b, a, 1)
        print("置換しました: " + label)
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
