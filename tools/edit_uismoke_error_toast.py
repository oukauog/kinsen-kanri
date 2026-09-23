# -*- coding: utf-8 -*-
"""
工事1-2: tests/ui_smoke_driver.js に「エラーの文言が画面に出るか」の確認を足す。

理由:
  auth.js の getRedirectResult() が失敗したとき（iPhone Safari の
  auth/missing-initial-state など）、利用者に見えるのは KKUI.toast のエラートーストだけ。
  その表示経路が生きているかを無人で確認できるようにしておく。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_error_toast.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

BEFORE = """        check('想定外の alert が出ていない', alerts.length === 0, alerts.join(' / '));
      })"""

AFTER = """        check('想定外の alert が出ていない', alerts.length === 0, alerts.join(' / '));

        // ログインの失敗（iPhone Safari の auth/missing-initial-state など）は
        // このトーストでしか利用者に見えないので、表示経路が生きているかを見る
        root.KKUI.toast('ログインに失敗しました: Firebase: Unable to process request ' +
          'due to missing initial state. (auth/missing-initial-state).', 'error');
        var toasts = document.querySelectorAll('.toast-box .toast.toast-error');
        var last = toasts[toasts.length - 1];
        check('ログイン失敗の文言が赤いトーストで画面に出る',
          !!last && last.textContent.indexOf('missing initial state') >= 0,
          last ? last.textContent : '(トーストが出ていない)');
      })"""


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
    if "missing initial state" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: エラートーストの確認を追加しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
