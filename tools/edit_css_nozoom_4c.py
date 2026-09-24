# -*- coding: utf-8 -*-
"""
工事4c: スマホ幅で入力欄の文字サイズを 16px にして、iOS Safari の自動ズームを止める。

不具合:
  iOS Safari は、フォーカスした入力欄の文字が 16px 未満だと画面を自動で拡大する。
  このアプリの .form-input は 0.9rem（14.4px）なので、支払いモーダルの
  日付・メモ・金額をタップするとズームし、body が position: fixed / overflow: hidden
  のため横スクロールで戻せず、画面の端が切れたままになる。

直し方:
  css/v2.css の既存の @media (max-width: 640px) の中に 16px の指定を足す。
  index.html の <style> にある .form-input { font-size: 0.9rem } に確実に勝たせるため、
  要素名 + クラス（input.form-input など＝詳細度 0,1,1）で書く。
  ・!important は使わない
  ・padding や高さは変えない（文字が大きい分だけ欄が少し高くなるのは許容）
  ・viewport の <meta> は触らない（ピンチ拡大を殺さないため）
  ・PC 幅（641px 以上）には一切影響しない（@media の中だけ）

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_nozoom_4c.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

# モバイルブロックの末尾（工事4b の最後の規則）に続けて足す
BEFORE = """  .transfer-names {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}"""

AFTER = """  .transfer-names {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* 工事4c: iOS Safari の自動ズーム対策。
     入力欄の文字が 16px 未満だとフォーカス時に画面が拡大され、
     body が position: fixed のため戻せなくなる。スマホ幅では 16px にする。
     index.html の .form-input（0.9rem）に勝たせるため、
     要素名 + クラス（詳細度 0,1,1）で指定する（!important は使わない）。
     padding は変えないので、欄の高さがわずかに増えるだけ。 */
  input.form-input,
  select.form-input,
  textarea.form-input,
  input.member-row-input {
    font-size: 16px;
  }
}"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "input.form-input" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1

    out = src.replace(before, after, 1)

    # 念のための健全性チェック
    if out.count("{") != out.count("}"):
        print("中止しました（波括弧の数が合いません）。ファイルは変更していません。")
        return 1
    # 今回足す「宣言」に !important が無いこと。
    # ・ファイル全体を見ると、工事1 からある [hidden] { display: none !important } に当たる
    # ・AFTER をそのまま見ると、説明コメントの中の文言に当たる
    # ので、コメントを取り除いた本体だけを調べる
    import re as _re
    added_body = _re.sub(r"/\*.*?\*/", "", AFTER, flags=_re.S)
    if "!important" in added_body:
        print("中止しました（追加する宣言に !important が入っています）。ファイルは変更していません。")
        return 1
    # @media の中に入ったこと（最後の @media 以降に追加分があること）を確認
    media_at = out.rfind("@media (max-width: 640px)")
    if media_at < 0 or out.find("input.form-input", media_at) < 0:
        print("中止しました（追加分がモバイル用 @media の中にありません）。ファイルは変更していません。")
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
