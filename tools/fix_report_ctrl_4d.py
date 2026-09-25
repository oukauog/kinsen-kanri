# -*- coding: utf-8 -*-
"""
工事4d-0: 報告書 2 本に入っている「生の制御文字」を文字表記（\\x00 / \\x1f / \\x7f）に書き換える。

対象:
  docs/reports/工事4b_報告.md
  docs/reports/本番切替_報告.md

経緯:
  migrate.js の BAD_KEY の不具合（生の制御文字がファイルに入っていた件）を説明する箇所で、
  報告書の本文にも同じ生の制御文字（NUL・0x1F・0x7F）が入ってしまい、
  git がこの 2 ファイルをバイナリ扱いしている。文章上は「\\x00」等と書いたつもりの箇所なので、
  バックスラッシュ + x + 16 進 2 桁の文字表記に置き換える。文章の意味は変わらない。

安全のため、次をすべて確認してから書き戻す（1 つでも違えば、どのファイルにも何も書かない）:
  ・置換前の制御文字の数が、調査時に数えた数と一致すること
  ・制御文字が現れる行はすべて、想定したキーワード（文字表記を説明している行）を含むこと
  ・置換後、制御文字（0x00〜0x08、0x0B、0x0C、0x0E〜0x1F、0x7F）が 0 個であること
  ・置換後も UTF-8 として読めること

実行: py -X utf8 tools/fix_report_ctrl_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ファイル名: (置換前に期待する各制御文字の数, 制御文字を含む行が必ず含むキーワード)
TARGETS = [
    (os.path.join(ROOT, "docs", "reports", "工事4b_報告.md"),
     {0x00: 1, 0x7F: 1},
     ["Migrate.isSafeKey"]),
    (os.path.join(ROOT, "docs", "reports", "本番切替_報告.md"),
     {0x00: 3, 0x1F: 2, 0x7F: 2},
     ["BAD_KEY", "エスケープ表記"]),
]

# 数える対象（依頼文の範囲 + DEL 0x7F）。\t \n \r は許す
CTRL = set(range(0x00, 0x09)) | {0x0B, 0x0C} | set(range(0x0E, 0x20)) | {0x7F}


def count_ctrl(data):
    counts = {}
    for b in data:
        if b in CTRL:
            counts[b] = counts.get(b, 0) + 1
    return counts


def to_notation(data):
    out = bytearray()
    for b in data:
        if b in CTRL:
            out += ("\\x%02x" % b).encode("ascii")
        else:
            out.append(b)
    return bytes(out)


def main():
    plans = []
    errors = []
    for path, expect, keywords in TARGETS:
        name = os.path.basename(path)
        with io.open(path, "rb") as f:
            src = f.read()
        before = count_ctrl(src)
        if not before and b"\\x00" in src:
            print("%s: すでに適用済みです。" % name)
            continue
        if before != expect:
            errors.append("%s: 制御文字の数が想定と違う（想定 %s、実際 %s）"
                          % (name, fmt(expect), fmt(before)))
            continue
        for line in src.split(b"\n"):
            if any(b in CTRL for b in line):
                text = line.decode("utf-8", "replace")
                if not any(k in text for k in keywords):
                    errors.append("%s: 想定外の行に制御文字がある: %r" % (name, text[:80]))
        out = to_notation(src)
        after = count_ctrl(out)
        if after:
            errors.append("%s: 置換後も制御文字が残る %s" % (name, fmt(after)))
        try:
            out.decode("utf-8")
        except UnicodeDecodeError as e:
            errors.append("%s: 置換後に UTF-8 として読めない: %s" % (name, e))
        plans.append((path, name, src, out, before, after))

    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    for path, name, src, out, before, after in plans:
        with io.open(path, "wb") as f:
            f.write(out)
        # 書き込んだものを読み直して数え直す
        with io.open(path, "rb") as f:
            check = count_ctrl(f.read())
        print("%s: 置換前 %s（計 %d） → 置換後 %d 個、%d → %d バイト"
              % (name, fmt(before), sum(before.values()), sum(check.values()), len(src), len(out)))
        if check:
            print("  エラー: 書き込み後も制御文字が残っています %s" % fmt(check))
            return 1
    print("完了")
    return 0


def fmt(counts):
    return "{" + ", ".join("0x%02X: %d" % (k, counts[k]) for k in sorted(counts)) + "}"


if __name__ == "__main__":
    sys.exit(main())
