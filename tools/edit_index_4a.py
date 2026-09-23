# -*- coding: utf-8 -*-
"""
工事4a: index.html に
  ① js/csv.js と js/env.js の読み込み
  ② ログイン画面のアプリ内ブラウザ案内（§5.1）
を足す。CSV 出力モーダル（v1 の死に DOM）はそのまま再利用するので触らない。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_index_4a.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")

REPLACEMENTS = []

# ① 読み込み: csv は calc/settle の後、env はどこでもよいので並べて置く
REPLACEMENTS.append((
    "js/csv.js と js/env.js の読み込みを追加",
    """<script src="js/settle.js"></script>
<script src="js/store.js"></script>""",
    """<script src="js/settle.js"></script>
<script src="js/csv.js"></script>
<script src="js/env.js"></script>
<script src="js/store.js"></script>"""))

# ② ログイン画面の案内（ログインボタンの上。ボタン自体は残す）
REPLACEMENTS.append((
    "アプリ内ブラウザの案内を追加",
    """    <button class="btn-google" id="btnLogin" onclick="doLogin()">Google でログイン</button>""",
    """    <div class="inapp-notice" id="inAppNotice" hidden>
      <div class="inapp-title">このアプリ内ブラウザでは Google ログインができません</div>
      <div class="inapp-body">右上（または下）のメニューから「Safari で開く」「Chrome で開く」を選んでください。</div>
      <button class="btn-copy-url" id="btnCopyUrl" onclick="copyPageUrl()">URL をコピー</button>
      <div class="inapp-url" id="inAppUrl" hidden></div>
    </div>
    <button class="btn-google" id="btnLogin" onclick="doLogin()">Google でログイン</button>"""))


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
    print("書き込み完了: %s（div %d 組、script %d 組）"
          % (TARGET, out.count("<div"), out.count("<script")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
