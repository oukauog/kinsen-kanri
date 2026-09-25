# -*- coding: utf-8 -*-
"""
工事7: icons/icon.svg（原本）から、ホーム画面アイコン・favicon の PNG を作る。

方法（依頼文の (b)）:
  1. icon.svg を埋めた最小の HTML を一時フォルダに作り、ヘッドレス Chrome で 512×512 を 1 枚だけ撮る
     （--window-size=512,512、--force-device-scale-factor=1、毎回新しい --user-data-dir）
  2. Pillow で RGB（透明なし）にし、LANCZOS で縮小して各サイズを書き出す

作るもの（すべて icons/）:
  apple-touch-icon.png 180×180 / icon-192.png 192×192 / icon-512.png 512×512 / favicon-32.png 32×32

生成用の一時 HTML と撮った原画像はリポジトリの外（一時フォルダ）に置き、終わったら消す。
出来た PNG の寸法がぴったりでなければ、何も書かずに終了する。

準備: Pillow（無ければ py -X utf8 -m pip install pillow）
実行: py -X utf8 tools/make_icons.py
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "icons")
SVG = os.path.join(ICONS, "icon.svg")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

BASE = 512
OUTPUTS = [
    ("icon-512.png", 512),
    ("icon-192.png", 192),
    ("apple-touch-icon.png", 180),
    ("favicon-32.png", 32),
]

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  html, body { margin: 0; padding: 0; width: %(n)dpx; height: %(n)dpx; overflow: hidden; background: #4f46e5; }
  svg { display: block; width: %(n)dpx; height: %(n)dpx; }
</style></head>
<body>%(svg)s</body></html>
"""


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def main():
    chrome = find_chrome()
    if not chrome:
        print("中止しました: Chrome が見つかりません")
        return 1
    with io.open(SVG, "r", encoding="utf-8") as f:
        svg = f.read()

    work = tempfile.mkdtemp(prefix="kk_icons_")
    profile = tempfile.mkdtemp(prefix="kk_prof_")
    try:
        page = os.path.join(work, "icon.html")
        shot = os.path.join(work, "shot.png")
        with io.open(page, "w", encoding="utf-8", newline="\n") as f:
            f.write(HTML % {"n": BASE, "svg": svg})
        r = subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--window-size=%d,%d" % (BASE, BASE),
            "--user-data-dir=" + profile,
            "--screenshot=" + shot,
            "file:///" + page.replace("\\", "/"),
        ], capture_output=True, timeout=120)
        if not os.path.exists(shot):
            print("中止しました: スクリーンショットが撮れませんでした")
            print(r.stderr.decode("utf-8", "replace")[-2000:])
            return 1

        src = Image.open(shot).convert("RGB")
        if src.size != (BASE, BASE):
            print("中止しました: 撮った画像が %dx%d（%dx%d であるべき）" % (src.size + (BASE, BASE)))
            return 1

        images = []
        for name, n in OUTPUTS:
            img = src.copy() if n == BASE else src.resize((n, n), Image.LANCZOS)
            if img.size != (n, n) or img.mode != "RGB":
                print("中止しました: %s が %s / %s" % (name, img.size, img.mode))
                return 1
            images.append((name, img))

        os.makedirs(ICONS, exist_ok=True)
        for name, img in images:
            path = os.path.join(ICONS, name)
            img.save(path, "PNG", optimize=True)
            print("書き込み完了: icons/%s %dx%d %d バイト" % (name, img.size[0], img.size[1], os.path.getsize(path)))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
