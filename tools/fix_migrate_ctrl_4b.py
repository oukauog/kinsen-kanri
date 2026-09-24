# -*- coding: utf-8 -*-
"""
工事4b-A: js/migrate.js の BAD_KEY の行に入っている「生の制御文字」を
エスケープ表記（\\x00 / \\x1f / \\x7f）に書き換える。挙動は変わらない。

経緯（docs/reports/本番切替_報告.md の「気づいた点」）:
  工事2 でこのファイルを作ったとき、正規表現の文字クラスに
  \\u0000 等と書いたつもりが、実際の制御文字（NUL・0x1F・0x7F の 3 バイト）が
  そのままファイルに入ってしまった。NUL があるため git がバイナリ扱いになり、
  差分が見えない・エディタで扱いづらい、という難点がある。
  正規表現としての意味は同じなので、動作は変わらない。

安全のため、次をすべて確認してから書き戻す（1 つでも違えば何も書かない）:
  ・BAD_KEY の行がちょうど 1 行あること
  ・対象の制御文字（0x00 / 0x1F / 0x7F）が、その行にちょうど 3 バイトあること
  ・ファイル全体でも、その 3 バイト以外に対象の制御文字が無いこと
  ・置換後、ファイル全体に 0x20 未満のバイトが \\n \\r \\t 以外に 1 つも無いこと

実行: py -X utf8 tools/fix_migrate_ctrl_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "migrate.js")

# 置換前後（バイト列で扱う。ソースに生の制御文字を書かないよう bytes で組み立てる）
BEFORE = b"  var BAD_KEY = /[.$#[\\]/" + bytes([0x00]) + b"-" + bytes([0x1F]) + bytes([0x7F]) + b"]/;"
AFTER = b"  var BAD_KEY = /[.$#[\\]/\\x00-\\x1f\\x7f]/;"

# 許してよい制御文字（改行・復帰・タブ）
ALLOWED = {0x09, 0x0A, 0x0D}


def ctrl_positions(data):
    """0x20 未満（許可分を除く）と 0x7F の位置を返す"""
    return [i for i, b in enumerate(data)
            if (b < 0x20 and b not in ALLOWED) or b == 0x7F]


def main():
    with io.open(TARGET, "rb") as f:
        src = f.read()
    print("置換前のサイズ: %d バイト" % len(src))

    if BEFORE not in src and AFTER in src:
        print("すでに適用済みです。何もしません。")
        return 0

    errors = []

    # ① BAD_KEY を定義している行がちょうど 1 行
    #    （BAD_KEY.test(k) で使っている行もあるので、定義だけを数える）
    lines = src.split(b"\n")
    hits = [i for i, l in enumerate(lines) if b"var BAD_KEY =" in l]
    if len(hits) != 1:
        errors.append("BAD_KEY を定義している行が %d 行（1 行であるべき）" % len(hits))

    # ② 置換対象がちょうど 1 か所
    n = src.count(BEFORE)
    if n != 1:
        errors.append("置換対象の一致が %d 件（1 件であるべき）" % n)

    # ③ 対象の制御文字はその行にちょうど 3 バイト、かつファイル全体でもそれだけ
    pos = ctrl_positions(src)
    if len(pos) != 3:
        errors.append("対象の制御文字がファイル全体で %d バイト（3 バイトであるべき）: 位置 %s"
                      % (len(pos), pos[:10]))
    elif len(hits) == 1:
        start = len(b"\n".join(lines[:hits[0]])) + (1 if hits[0] > 0 else 0)
        end = start + len(lines[hits[0]])
        outside = [p for p in pos if not (start <= p < end)]
        if outside:
            errors.append("BAD_KEY の行の外に制御文字がある: 位置 %s" % outside)

    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src.replace(BEFORE, AFTER, 1)

    # ④ 置換後に制御文字が残っていないこと
    left = ctrl_positions(out)
    if left:
        print("中止しました（置換後も制御文字が残っています: 位置 %s）。ファイルは変更していません。" % left[:10])
        return 1
    if b"\x00" in out:
        print("中止しました（NUL バイトが残っています）。ファイルは変更していません。")
        return 1

    with io.open(TARGET, "wb") as f:
        f.write(out)

    print("置換後のサイズ: %d バイト（%+d）" % (len(out), len(out) - len(src)))
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
