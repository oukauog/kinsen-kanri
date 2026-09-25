# -*- coding: utf-8 -*-
"""
工事4d-B: スマホ幅（@media (max-width: 640px)）で、過去の清算の送金行を 2 段にする。

  ・.transfer-by（✓ 名前 日時）を display: block; margin-left: 0 にして、名前の下の行に置く
    （長いときは 1 行のまま … で省略する）
  ・名前（.transfer-pair）は今までどおり nowrap + ellipsis で 1 行に収める
    （text-overflow は block の要素にしか効かないので .transfer-pair を block にする。
     これまで .transfer-names に付けていた nowrap + ellipsis は .transfer-pair へ移す）
  ・.transfer-names は overflow: hidden のまま（中身が行の外へ出ないための保険）

PC 幅（641px 以上）の規則には触らない。
測定（tests/ui_smoke_driver.js の 工事4d-B）では、ヘッドレス Chrome の 375px で
モーダル・.past-settlement・.transfer-row のはみ出しは修正前から出ていなかったため、
横スクロールの原因を直す変更はしていない。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_pastwidth_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

BEFORE = """  .transfer-by { font-size: 0.65rem; margin-left: 6px; }
  .transfer-names {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
"""

AFTER = """  /* 工事4d: 「✓ 名前 日時」は名前の下の行に置く（1 行に詰め込まない）。
     名前（.transfer-pair）は 1 行に収め、長ければ … で省略する */
  .transfer-by {
    display: block;
    margin-left: 0;
    font-size: 0.65rem;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .transfer-names { overflow: hidden; }
  .transfer-pair {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "  .transfer-pair {" in src:
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
