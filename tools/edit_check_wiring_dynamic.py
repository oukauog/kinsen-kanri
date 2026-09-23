# -*- coding: utf-8 -*-
"""
工事3: tools/check_wiring.py を、ui.js が自分で作る id にも対応させる。

これまでは「ui.js が $('xxx') で探す id は index.html にあるはず」という前提だったが、
工事3 で ui.js が組み立てる HTML の中に id を置くようになった
（例: 清算モーダルの「この内容で清算する」ボタン settleConfirmBtn）。
ui.js の中で id="xxx" として作られているものは、実在する id として扱う。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_check_wiring_dynamic.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tools", "check_wiring.py")

BEFORE = '''    # HTML が参照している id を ui.js が $('...') で引いているか（逆方向の確認）
    html_ids = set(re.findall(r'\\sid="([^"]+)"', html))
    ui_ids = set(re.findall(r"\\$\\('([^']+)'\\)", ui))
    ui_ids |= set(re.findall(r'getElementById\\([\\'"]([^\\'"]+)[\\'"]\\)', ui))
    missing_ids = sorted(i for i in ui_ids if i not in html_ids and i != "toastBox")'''

AFTER = '''    # HTML が参照している id を ui.js が $('...') で引いているか（逆方向の確認）
    html_ids = set(re.findall(r'\\sid="([^"]+)"', html))
    # ui.js が自分で組み立てる HTML の中に置いた id も「実在する」として扱う
    made_by_ui = set(re.findall(r'id="([A-Za-z_][\\w-]*)"', ui))
    made_by_ui |= set(re.findall(r"\\.id\\s*=\\s*'([^']+)'", ui))
    ui_ids = set(re.findall(r"\\$\\('([^']+)'\\)", ui))
    ui_ids |= set(re.findall(r'getElementById\\([\\'"]([^\\'"]+)[\\'"]\\)', ui))
    missing_ids = sorted(i for i in ui_ids if i not in html_ids and i not in made_by_ui)'''


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    if "made_by_ui" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: 動的に作る id に対応しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
