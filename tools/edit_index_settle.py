# -*- coding: utf-8 -*-
"""
工事3: index.html に
  ① js/settle.js の読み込み
  ② 支払い入力モーダルの「金額確認中」チェックボックス
  ③ 清算モーダルの中身の入れ替え（固定文を外し、幅を広げる）
を足す。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_index_settle.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")

REPLACEMENTS = []

# ① 読み込み順: calc → migrate → settle → store（settle は calc を使う）
REPLACEMENTS.append((
    "js/settle.js の読み込みを追加",
    """<script src="js/migrate.js"></script>
<script src="js/store.js"></script>""",
    """<script src="js/migrate.js"></script>
<script src="js/settle.js"></script>
<script src="js/store.js"></script>"""))

# ② 金額欄の直下に「金額確認中」
REPLACEMENTS.append((
    "支払いモーダルに金額確認中のチェックを追加",
    """      <input type="number" class="form-input" id="payAmount" placeholder="0" min="0" step="1">
    </div>""",
    """      <input type="number" class="form-input" id="payAmount" placeholder="0" min="0" step="1">
      <label class="check-row">
        <input type="checkbox" id="payPending" onchange="onPendingToggle()">
        <span>金額確認中（あとで金額を入れる）</span>
      </label>
      <div class="check-hint" id="payPendingHint">確認中の支払いは残高と清算の計算に入りません</div>
    </div>"""))

# ③ 清算モーダル: 固定の説明文を外し（中身は ui.js が組み立てる）、少し広くする
REPLACEMENTS.append((
    "清算モーダルの固定文を外す",
    """    <div class="modal-title">&#x1F9FE; &#x6E05;&#x7B97;</div>
    <p style="font-size:0.85rem;color:var(--gray-500);margin-bottom:16px">
      &#x4EE5;&#x4E0B;&#x306E;&#x652F;&#x6255;&#x3044;&#x3092;&#x884C;&#x3046;&#x3068;&#x8CB8;&#x3057;&#x501F;&#x308A;&#x304C;&#x30C1;&#x30E3;&#x30E9;&#x306B;&#x306A;&#x308A;&#x307E;&#x3059;&#x3002;
    </p>
    <div id="settlementContent"></div>""",
    """    <div class="modal-title">&#x1F9FE; &#x6E05;&#x7B97;</div>
    <div id="settlementContent"></div>"""))

REPLACEMENTS.append((
    "清算モーダルを少し広くする",
    """<!-- Modal: &#x6E05;&#x7B97; -->
<div class="modal-overlay" id="settlementModal">
  <div class="modal">""",
    """<!-- Modal: &#x6E05;&#x7B97; -->
<div class="modal-overlay" id="settlementModal">
  <div class="modal modal-wide">"""))


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors, plan = [], []
    for label, before, after in REPLACEMENTS:
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

    assert out.count("<div") == out.count("</div>"), \
        "div の開閉が合わない: %d / %d" % (out.count("<div"), out.count("</div>"))
    assert out.count("<script") == out.count("</script>")
    assert out.count("<label") == out.count("</label>")
    assert "</body>" in out and "</html>" in out

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: %s（div %d 組、script %d 組、label %d 組）"
          % (TARGET, out.count("<div"), out.count("<script"), out.count("<label")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
