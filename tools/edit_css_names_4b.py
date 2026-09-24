# -*- coding: utf-8 -*-
"""
工事4b-B: css/v2.css に入力者・確定者・チェックした人の表示のスタイルを足す。
スマホ幅で名前が長くても 1 行に収まるようにする（ellipsis）。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_names_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

ANCHOR = """/* ── モバイル ───────────────────────────────── */
@media (max-width: 640px) {"""

ADDITION = """/* ── 誰が入力したか・誰がチェックしたか（工事4b）──── */
.payment-by {
  font-size: 0.7rem;
  color: var(--gray-500);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.past-by {
  font-size: 0.72rem;
  color: var(--gray-500);
  max-width: 45%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.transfer-by {
  font-size: 0.7rem;
  color: var(--gray-500);
  margin-left: 8px;
  white-space: nowrap;
}
.transfer-row.done .transfer-by { text-decoration: none; }

"""

MOBILE_ANCHOR = """  .transfer-row { font-size: 0.8rem; gap: 7px; }
  .past-settlement { padding: 11px 12px; }
}"""

MOBILE_ADD = """  .transfer-row { font-size: 0.8rem; gap: 7px; }
  .past-settlement { padding: 11px 12px; }

  /* 工事4b: 名前が長くても 1 行に収める */
  .payment-by { font-size: 0.65rem; }
  .past-by { font-size: 0.68rem; max-width: 100%; }
  .transfer-by { font-size: 0.65rem; margin-left: 6px; }
  .transfer-names {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if ".payment-by" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    pairs = [
        ("入力者・確定者のスタイルを追加", fix(ANCHOR), fix(ADDITION) + fix(ANCHOR)),
        ("モバイル用の調整を追加", fix(MOBILE_ANCHOR), fix(MOBILE_ADD)),
    ]
    for label, before, after in pairs:
        if src.count(before) != 1:
            print("中止しました（%s: 一致 %d 件）。ファイルは変更していません。"
                  % (label, src.count(before)))
            return 1

    out = src
    for label, before, after in pairs:
        out = out.replace(before, after, 1)
        print("置換しました: " + label)

    if out.count("{") != out.count("}"):
        print("中止しました（波括弧の数が合いません）")
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
