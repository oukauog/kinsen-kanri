# -*- coding: utf-8 -*-
"""
index.html に起動中（ログイン状態が分かるまで）の画面を足す。

Firebase がログイン状態を返すまでの 0.5〜1 秒、ログイン画面もアプリ画面も
出せない時間がある。そのままだと真っ白になるので、その間だけ出す画面を足す。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_index_boot.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")

BEFORE = """<div class="login-screen" id="loginScreen" hidden>"""

AFTER = """<div class="login-screen" id="bootScreen">
  <div class="login-card">
    <div class="login-icon">&#x1F4B0;</div>
    <div class="login-title">金銭管理ツール</div>
    <p class="login-desc">読み込み中…</p>
  </div>
</div>

<div class="login-screen" id="loginScreen" hidden>"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"
    before = BEFORE.replace("\n", nl) if nl != "\n" else BEFORE
    after = AFTER.replace("\n", nl) if nl != "\n" else AFTER

    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    if 'id="bootScreen"' in src:
        print("すでに適用済みです。何もしません。")
        return 0

    out = src.replace(before, after, 1)
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: 起動中画面を追加しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
