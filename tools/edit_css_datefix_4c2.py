# -*- coding: utf-8 -*-
"""
工事4c-2: スマホ幅で入力欄の高さを明示して揃える（日付欄だけ伸びる問題の修正）。

不具合:
  工事4c で文字を 16px にしたら、iOS Safari では「支払いを記録」の日付欄
  （#payDate、input[type="date"]）だけ枠が不自然に伸び、他の欄と揃わなくなった。
  iOS は type="date" を独自の内部部品で描くため、文字サイズ + padding から
  高さ・幅を素直に計算しない（14.4px のときは偶然揃っていた）。

直し方:
  ・スマホ幅の入力欄すべてに同じ高さ（40px）を明示する。
    box-sizing: border-box が * で効いているので、外寸がそのまま揃う。
    textarea だけは複数行なので height ではなく min-height にする
    （現在このアプリに textarea は 1 つも無い。将来足したときの保険）。
  ・日付欄には iOS の独自描画を抑える指定を足す。

  padding（9px 12px）・border・border-radius・色は変えない。
  PC 幅（641px 以上）には一切影響しない（@media の中だけ）。
  !important は使わない。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_datefix_4c2.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

# 工事4c で足した規則の直後に続ける
BEFORE = """  input.form-input,
  select.form-input,
  textarea.form-input,
  input.member-row-input {
    font-size: 16px;
  }
}"""

AFTER = """  input.form-input,
  select.form-input,
  textarea.form-input,
  input.member-row-input {
    font-size: 16px;
  }

  /* 工事4c-2: 入力欄の高さを明示して揃える。
     iOS Safari は input[type="date"] を独自の内部部品で描くため、
     文字サイズ + padding から高さ・幅を素直に計算せず、日付欄だけ伸びていた。
     16px の文字 + 上下 padding 9px + 枠 1px を見込んで 40px に統一する
     （box-sizing: border-box が * で効いているので、これが外寸になる）。
     padding・border・角丸・色は変えない。 */
  input.form-input,
  select.form-input,
  input.member-row-input {
    height: 40px;
  }

  /* textarea は複数行なので高さを固定しない（現在このアプリには無い。将来用の保険）*/
  textarea.form-input {
    min-height: 40px;
  }

  /* 日付欄だけ iOS の独自描画を抑える。
     appearance を切って、幅と行の高さを他の欄と同じ土俵に乗せる。 */
  input[type="date"].form-input {
    -webkit-appearance: none;
    appearance: none;
    display: block;
    width: 100%;
    min-width: 0;
    line-height: normal;
  }

  /* iOS で日付の値が中央寄せになる既知の癖への対処（左寄せに揃える）*/
  input[type="date"].form-input::-webkit-date-and-time-value {
    text-align: left;
  }
}"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "date-and-time-value" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1

    out = src.replace(before, after, 1)

    # 健全性チェック
    if out.count("{") != out.count("}"):
        print("中止しました（波括弧の数が合いません）。ファイルは変更していません。")
        return 1

    # 今回足す「宣言」に !important が無いこと
    # （ファイル全体だと工事1 からある [hidden] の分に、AFTER 全体だと説明文に当たるため、
    #   コメントを取り除いた本体だけを見る）
    added_body = re.sub(r"/\*.*?\*/", "", AFTER, flags=re.S)
    if "!important" in added_body:
        print("中止しました（追加する宣言に !important が入っています）。ファイルは変更していません。")
        return 1

    # padding / border / border-radius / color を触っていないこと
    for prop in ("padding", "border:", "border-radius", "color:", "background"):
        if prop in added_body:
            print("中止しました（追加分が %s を変更しています）。ファイルは変更していません。" % prop)
            return 1

    # 追加分がモバイル用 @media の中にあること
    media_at = out.rfind("@media (max-width: 640px)")
    if media_at < 0 or out.find("date-and-time-value", media_at) < 0:
        print("中止しました（追加分がモバイル用 @media の中にありません）。ファイルは変更していません。")
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
