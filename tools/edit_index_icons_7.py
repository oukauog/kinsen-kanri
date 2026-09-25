# -*- coding: utf-8 -*-
"""
工事7: index.html の head に、アイコン・manifest・タブの色のタグを 6 行足す（<title> の直後）。

  <link rel="icon" type="image/svg+xml" href="icons/icon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="icons/apple-touch-icon.png">
  <link rel="manifest" href="site.webmanifest">
  <meta name="theme-color" content="#4f46e5">
  <meta name="apple-mobile-web-app-title" content="金銭管理">

apple-mobile-web-app-capable は付けない（全画面モードにすると iOS で Google ログインのリダイレクトが壊れる恐れ）。
既に似たタグ（rel="icon" / apple-touch-icon / manifest / theme-color / apple-mobile-web-app-*）があれば、何も書かずに終了する。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_index_icons_7.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")

BEFORE = """  <title>金銭管理ツール</title>
"""
AFTER = """  <title>金銭管理ツール</title>
  <link rel="icon" type="image/svg+xml" href="icons/icon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="icons/apple-touch-icon.png">
  <link rel="manifest" href="site.webmanifest">
  <meta name="theme-color" content="#4f46e5">
  <meta name="apple-mobile-web-app-title" content="金銭管理">
"""

SIMILAR = re.compile(r'rel="(?:shortcut )?icon"|apple-touch-icon|rel="manifest"|theme-color|apple-mobile-web-app')


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if fix(AFTER) in src:
        print("すでに適用済みです。何もしません。")
        return 0
    found = SIMILAR.findall(src)
    if found:
        print("中止しました（似たタグが既にあります: %s）。ファイルは変更していません。" % ", ".join(sorted(set(found))))
        return 1
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
