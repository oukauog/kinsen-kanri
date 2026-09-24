# -*- coding: utf-8 -*-
"""
工事4b-B（表示）: js/ui.js に
  ① 履歴行に「入力: <名前>」（createdByName がある支払いだけ）
  ② 過去の清算の見出しに「<名前> が確定」
  ③ 送金行のチェック済み表示に「✓ <名前> MM/DD HH:mm」
を足す。

無い項目は「無いまま」扱う（「不明」等の文字は出さない）。
移行で入った支払いや工事4b 以前の入力には名前が無いので、何も出ない。これで正しい。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_names_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

REPLACEMENTS = []

# ① 送金チェックの横に出す短い日時
REPLACEMENTS.append((
    "短い日時の表記を足す",
    """  /** 開いているグループの清算レコード（無ければ {}） */""",
    """  /** ミリ秒 → 「09/24 18:30」（送金チェックの横に出す短い形） */
  function shortDateTime(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return p(d.getMonth() + 1) + '/' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** 開いているグループの清算レコード（無ければ {}） */"""))

# ② 履歴行に入力者
REPLACEMENTS.append((
    "履歴行に入力者を出す",
    """            '<div class="payment-participants">' + esc(partNames) + '</div>' +
          '</div>' +""",
    """            '<div class="payment-participants">' + esc(partNames) + '</div>' +
            // 入力者は、名前が保存されている支払いだけ（移行分・工事4b 以前には無い）
            (p.createdByName
              ? '<div class="payment-by">入力: ' + esc(p.createdByName) + '</div>' : '') +
          '</div>' +"""))

# ③ 清算の見出しに確定者、送金行にチェックした人
REPLACEMENTS.append((
    "清算の見出しと送金行に名前を出す",
    """            '<span class="past-count">対象 ' + Settle.targetCount(s) + ' 件</span>' +
            (Settle.allDone(s) ? '<span class="past-done-badge">完了</span>' : '') +
          '</div>' +
          transfers.map(function (t) {
            return '<label class="transfer-row' + (t.done ? ' done' : '') + '">' +
              '<input type="checkbox"' + (t.done ? ' checked' : '') +
              ' onchange="toggleTransferDone(\\'' + s.id + '\\', \\'' + t.id + '\\', this.checked)">' +
              '<span class="transfer-names">' + esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + '</span>' +
              '<span class="transfer-amount">' + money(t.amount) + '</span></label>';
          }).join('') +""",
    """            '<span class="past-count">対象 ' + Settle.targetCount(s) + ' 件</span>' +
            // 確定した人は、名前が保存されている清算だけ
            (s.createdByName
              ? '<span class="past-by">' + esc(s.createdByName) + ' が確定</span>' : '') +
            (Settle.allDone(s) ? '<span class="past-done-badge">完了</span>' : '') +
          '</div>' +
          transfers.map(function (t) {
            // チェック済みの印: 名前があれば「✓ 名前 09/24 18:30」、無ければ日時だけ
            var mark = '';
            if (t.done) {
              var who = t.doneByName ? esc(t.doneByName) + ' ' : '';
              var when = shortDateTime(t.doneAt);
              if (who || when) mark = '<span class="transfer-by">&#x2713; ' + who + when + '</span>';
            }
            return '<label class="transfer-row' + (t.done ? ' done' : '') + '">' +
              '<input type="checkbox"' + (t.done ? ' checked' : '') +
              ' onchange="toggleTransferDone(\\'' + s.id + '\\', \\'' + t.id + '\\', this.checked)">' +
              '<span class="transfer-names">' + esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + mark + '</span>' +
              '<span class="transfer-amount">' + money(t.amount) + '</span></label>';
          }).join('') +"""))


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors, plan = [], []
    for label, before, after in REPLACEMENTS:
        b = fix(before)
        n = src.count(b)
        if n != 1:
            errors.append("%s: 一致 %d 件（1 件であるべき）" % (label, n))
        plan.append((label, b, fix(after)))

    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for label, b, a in plan:
        out = out.replace(b, a, 1)
        print("置換しました: " + label)

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
