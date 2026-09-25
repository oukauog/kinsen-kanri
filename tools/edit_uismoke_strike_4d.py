# -*- coding: utf-8 -*-
"""
工事4d-A: 画面の通し確認に「打ち消し線が『A → B』だけに付くこと」の確認を足す。

確認すること（工事4b-B の「送金チェックにチェックした人と日時が出る」の直後）:
  ・チェック済みの行で .transfer-pair の textDecorationLine に line-through が入っている
  ・.transfer-by 自身の textDecorationLine は none
  ・inline の線の伝播は computed style に出ないので、DOM でも確かめる:
    .transfer-by が .transfer-pair の中に無く、.transfer-names の直下で .transfer-pair の後ろにあること、
    .transfer-by から行（.transfer-row）までの祖先のどれにも line-through が付いていないこと

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_strike_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

EDITS = [(
"""          by ? by.textContent : '(表示が無い)');
        root.closeModal('settlementModal');
        return wait(40);
      })
""",
"""          by ? by.textContent : '(表示が無い)');

        // 工事4d-A: 打ち消し線は「A → B」だけ。「✓ 名前 日時」には付けない
        var row = by ? by.closest('.transfer-row') : null;
        var pair = row ? row.querySelector('.transfer-pair') : null;
        var names = row ? row.querySelector('.transfer-names') : null;
        var deco = function (el) { return getComputedStyle(el).textDecorationLine; };
        check('チェック済みの行: 「A → B」（.transfer-pair）に打ち消し線が付く',
          !!pair && deco(pair).indexOf('line-through') >= 0,
          pair ? deco(pair) : '(.transfer-pair が無い)');
        check('チェック済みの行: .transfer-by 自身には打ち消し線が付かない',
          !!by && deco(by).indexOf('line-through') < 0, by ? deco(by) : '');
        check('チェック済みの行: .transfer-by は .transfer-pair の外（.transfer-names の直下、後ろ）にある',
          !!by && !!pair && !!names && !by.closest('.transfer-pair') &&
          by.parentNode === names && pair.parentNode === names &&
          !!(pair.compareDocumentPosition(by) & Node.DOCUMENT_POSITION_FOLLOWING),
          by && by.parentNode ? by.parentNode.className : '');
        var lined = [];
        for (var el = by ? by.parentElement : null; el && el !== row.parentElement; el = el.parentElement) {
          if (deco(el).indexOf('line-through') >= 0) lined.push(el.className);
        }
        check('チェック済みの行: .transfer-by の祖先（行まで）に打ち消し線が無い（線が伝わらない）',
          !!by && lined.length === 0, lined.join(','));
        root.closeModal('settlementModal');
        return wait(40);
      })
""",
)]


def apply(path, edits, marker):
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if marker in src:
        print("すでに適用済みです。何もしません: " + path)
        return 0
    errors = []
    for before, _ in edits:
        n = src.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    out = src
    for before, after in edits:
        out = out.replace(fix(before), fix(after), 1)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + path)
    return 0


if __name__ == "__main__":
    sys.exit(apply(TARGET, EDITS, "工事4d-A"))
