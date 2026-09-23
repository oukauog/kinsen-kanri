# -*- coding: utf-8 -*-
"""
工事4a: css/v2.css にアプリ内ブラウザの案内と CSV モーダルの注記のスタイルを足す。
末尾のモバイル用 @media の直前に差し込む。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_4a.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

ANCHOR = """/* ── モバイル ───────────────────────────────── */
@media (max-width: 640px) {"""

ADDITION = """/* ── アプリ内ブラウザの案内（§5.1）──────────────── */
.inapp-notice {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  border-radius: 10px;
  padding: 13px 14px;
  margin-bottom: 16px;
  text-align: left;
  line-height: 1.6;
}
.inapp-title { font-size: 0.85rem; font-weight: 700; margin-bottom: 5px; }
.inapp-body { font-size: 0.8rem; }
.btn-copy-url {
  margin-top: 10px;
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid #d97706;
  background: white;
  color: #92400e;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-copy-url:hover { background: #fef3c7; }
.inapp-url {
  margin-top: 8px;
  font-size: 0.72rem;
  word-break: break-all;
  user-select: all;
  background: white;
  border: 1px dashed #fbbf24;
  border-radius: 6px;
  padding: 7px 9px;
}

/* ── CSV 出力モーダルの注記 ───────────────────── */
.export-note {
  font-size: 0.78rem;
  color: var(--gray-500);
  line-height: 1.6;
  margin-top: 12px;
}

"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if ".inapp-notice" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    anchor = fix(ANCHOR)
    if src.count(anchor) != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。"
              % src.count(anchor))
        return 1

    out = src.replace(anchor, fix(ADDITION) + anchor, 1)
    if out.count("{") != out.count("}"):
        print("中止しました（波括弧の数が合いません）")
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
