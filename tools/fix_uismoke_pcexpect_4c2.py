# -*- coding: utf-8 -*-
"""
工事4c-2: 通し確認の期待値の直し（PC 幅）。

実測して分かったこと:
  Chrome では PC 幅でも input[type="date"] は他の欄より数 px 高い
  （日付=43px / メモ=40px / 金額=40px / 支払った人=42px）。
  これは**工事4c-2 の前から同じ**で、今回の変更は @media (max-width: 640px) の
  中だけなので PC には届かない。

  つまり「PC 幅では日付欄とメモ欄の高さが等しい」という期待値が事実と違っていた
  （実装ではなくテスト側の思い込み）。

正しい確認は「PC は工事4c-2 の前と同じままか」なので、
  ・高さが 40px に固定されていないこと（＝スマホ用の規則が漏れていない）
  ・日付欄がメモ欄より高いという Chrome 既定のままであること
を見るように直す。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/fix_uismoke_pcexpect_4c2.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

BEFORE = """          check('PC 幅: 日付欄とメモ欄の高さが等しい（工事4c 以前と同じ）',
            near(m.payDate.h, m.payMemo.h),
            'date=' + m.payDate.h + ' / memo=' + m.payMemo.h);"""

AFTER = """          // Chrome は PC 幅でも日付欄を数 px 高く描く（工事4c-2 の前からそう）。
          // 今回の規則は @media (max-width: 640px) の中だけなので PC には届かない。
          // 「揃っていること」ではなく「前と同じままか」を見る。
          check('PC 幅: 日付欄は Chrome 既定のまま（スマホ用の高さ指定が漏れていない）',
            m.payDate.h > m.payMemo.h,
            'date=' + m.payDate.h + ' / memo=' + m.payMemo.h);"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "スマホ用の高さ指定が漏れていない" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: PC 幅の期待値を実態に合わせました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
