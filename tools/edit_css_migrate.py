# -*- coding: utf-8 -*-
"""
工事2: css/v2.css にオフラインバナーと取り込みダイアログ用のスタイルを足す。
末尾のモバイル用 @media の直前に差し込む（モバイル指定が最後に来る並びを保つ）。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_migrate.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

ANCHOR = """/* ── モバイル ───────────────────────────────── */
@media (max-width: 640px) {"""

ADDITION = """/* ── オフラインの帯（§5.7）───────────────────── */
.offline-banner {
  flex-shrink: 0;
  background: #fef3c7;
  color: #92400e;
  border-bottom: 1px solid #fde68a;
  font-size: 0.8rem;
  line-height: 1.4;
  padding: 7px 14px;
  text-align: center;
}

/* ── 旧バージョンからの取り込み ───────────────── */
.migrate-note { font-size: 0.85rem; color: var(--gray-700); line-height: 1.7; margin-bottom: 14px; }
.migrate-pick-list { display: flex; flex-direction: column; gap: 8px; }
.migrate-pick {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1.5px solid var(--gray-300);
  border-radius: 10px;
  cursor: pointer;
}
.migrate-pick:hover { background: var(--gray-50); }
.migrate-pick input { margin-top: 3px; flex-shrink: 0; }
.migrate-pick-name { font-size: 0.92rem; font-weight: 600; }
.migrate-pick-sub { font-size: 0.78rem; color: var(--gray-500); margin-top: 3px; }
.migrate-skip { font-size: 0.78rem; color: var(--gray-500); line-height: 1.6; margin-top: 14px; }

.migrate-result-list { display: flex; flex-direction: column; gap: 10px; }
.migrate-result-item {
  border: 1px solid var(--gray-200);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--gray-50);
}
.migrate-result-name { font-size: 0.92rem; font-weight: 600; }
.migrate-result-code {
  font-family: monospace;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  margin-top: 6px;
  display: inline-block;
  cursor: pointer;
  user-select: all;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px dashed var(--gray-300);
  background: white;
}
.migrate-result-code:hover { border-color: var(--primary); }
.migrate-result-tag { font-size: 0.72rem; color: var(--gray-500); margin-left: 8px; }

"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    anchor = fix(ANCHOR)
    n = src.count(anchor)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    if ".offline-banner" in src:
        print("すでに適用済みです。何もしません。")
        return 0

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
