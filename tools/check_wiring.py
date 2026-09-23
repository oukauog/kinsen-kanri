# -*- coding: utf-8 -*-
"""
index.html の onclick / onkeydown / oninput から呼ばれる関数が
js/ui.js で global（window.xxx）に生えているかを確認する。

インライン script を外に出したので、名前を 1 つ書き間違えるだけで
「押しても何も起きないボタン」ができる。それを機械で潰すための確認用。
HTML 側で参照している id が実在するかも一緒に見る。

実行: py -X utf8 tools/check_wiring.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 工事1 では画面から開けないモーダル（工事4 で復元する v1 の取込・出力まわり）
KNOWN_DEAD = {
    "downloadTemplate", "handleImport", "openExportModal", "openImportModal",
    "saveGroupRename", "openRenameGroupModal",
}


def read(path):
    with io.open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return f.read()


def main():
    html = read("index.html")
    ui = read("js/ui.js")

    # HTML のイベント属性から呼ばれている関数名
    called = set()
    for attr in re.findall(r'on(?:click|keydown|input|change)="([^"]*)"', html):
        # 直前が「.」のものはメソッド呼び出し（document.getElementById(...) 等）なので除く
        for name in re.findall(r'(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(', attr):
            called.add(name)
    called -= {"if", "for", "while", "return"}

    # ui.js が global に置いている関数名
    exported = set(re.findall(r'^\s*root\.([A-Za-z_$][\w$]*)\s*=', ui, re.M))

    missing = sorted(n for n in called if n not in exported and n not in KNOWN_DEAD)
    dead = sorted(n for n in called if n in KNOWN_DEAD)

    # HTML が参照している id を ui.js が $('...') で引いているか（逆方向の確認）
    html_ids = set(re.findall(r'\sid="([^"]+)"', html))
    ui_ids = set(re.findall(r"\$\('([^']+)'\)", ui))
    ui_ids |= set(re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)', ui))
    missing_ids = sorted(i for i in ui_ids if i not in html_ids and i != "toastBox")

    ok = True
    if missing:
        ok = False
        print("【NG】HTML から呼ばれているのに ui.js が global に出していない関数:")
        for n in missing:
            print("  - " + n)
    if missing_ids:
        ok = False
        print("【NG】ui.js が探しているのに HTML に無い id:")
        for i in missing_ids:
            print("  - " + i)

    if dead:
        print("【注意】工事1 では画面から開けない（工事4 で復元）: " + ", ".join(dead))

    print("HTML から呼ばれる関数 %d 個 / ui.js の global %d 個" % (len(called), len(exported)))
    print("結果: " + ("OK" if ok else "NG"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
