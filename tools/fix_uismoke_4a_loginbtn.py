# -*- coding: utf-8 -*-
"""
工事4a: 通し確認の直し。

「案内が出てもログインボタンは残る」の確かめ方が間違っていた。
`offsetParent !== null` は「いま画面に見えているか」の判定なので、
ログイン済みでログイン画面が隠れている状態では必ず失敗する（実装は正しい）。
ボタンが存在して、自分自身が隠されておらず、押せる状態かを見るように直す。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/fix_uismoke_4a_loginbtn.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

BEFORE = """          check('案内が出てもログインボタンは残る（誤判定に備える）',
            !!$('btnLogin') && $('btnLogin').offsetParent !== null);"""

AFTER = """          check('案内が出てもログインボタンは残る（誤判定に備える）',
            !!$('btnLogin') && $('btnLogin').hidden === false &&
            $('btnLogin').disabled === false &&
            $('btnLogin').textContent.indexOf('Google') >= 0,
            $('btnLogin') ? $('btnLogin').textContent : '(ボタンが無い)');"""


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

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: ログインボタンの確かめ方を直しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
