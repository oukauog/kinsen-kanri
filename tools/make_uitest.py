# -*- coding: utf-8 -*-
"""
index.html から「画面の通し確認用ページ」_uitest_tmp.html を作る。

  ・Firebase の読み込みと firebase-init / store / auth を tests/ui_smoke_fakes.js に差し替える
  ・最後に tests/ui_smoke_driver.js を足して、画面操作を自動で走らせる

index.html 自体は読むだけで変更しない。生成物 _uitest_tmp.html は確認用なので
git に入れず、確認が済んだら消す。

実行:
  py -X utf8 tools/make_uitest.py
  py -m http.server 8000
  ブラウザ（またはヘッドレス）で http://localhost:8000/_uitest_tmp.html
  → タイトルが UI-SMOKE-PASS になれば通過。中身は body の data-smoke 属性
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "_uitest_tmp.html")

# 置換前は index.html 内に 1 回だけ現れること
CUTS = [
    '<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>\n',
    '<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js"></script>\n',
    '<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>\n',
    # 工事5: SortableJS も外す（CDN が読めないときに一覧が今までどおり動くことを確かめる）
    '<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>\n',
    '<script src="js/firebase-init.js"></script>\n',
    '<script src="js/store.js"></script>\n',
    '<script src="js/auth.js"></script>\n',
]
ANCHOR = '<script src="js/ui.js"></script>'
REPLACEMENT = ('<script src="tests/ui_smoke_fakes.js"></script>\n'
               '<script src="js/ui.js"></script>\n'
               '<script src="tests/ui_smoke_driver.js"></script>')


def main():
    with io.open(SRC, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors = []
    for c in CUTS:
        if src.count(fix(c)) != 1:
            errors.append("一致 %d 件: %s" % (src.count(fix(c)), c.strip()))
    if src.count(fix(ANCHOR)) != 1:
        errors.append("一致 %d 件: %s" % (src.count(fix(ANCHOR)), ANCHOR))
    if errors:
        print("中止しました。index.html の構成が想定と違います:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for c in CUTS:
        out = out.replace(fix(c), "", 1)
    out = out.replace(fix(ANCHOR), fix(REPLACEMENT), 1)

    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("作成しました: " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
