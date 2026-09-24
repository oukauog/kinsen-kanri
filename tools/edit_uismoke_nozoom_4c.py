# -*- coding: utf-8 -*-
"""
工事4c: 画面の通し確認に「スマホ幅で入力欄が 16px になる」確認を足す。

確認すること:
  ・幅 390px（iPhone 相当）で支払いモーダルを開き、
    日付・メモ・金額の .form-input と、メンバー追加の .member-row-input が
    getComputedStyle で 16px になっていること
  ・幅 1024px（PC 相当）では .form-input が 14.4px（0.9rem）のままであること

ヘッドレスのウィンドウ幅は変えられないので、iframe を作ってその中に
確認用ページを読み込み、iframe の幅で @media を効かせて測る。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_nozoom_4c.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

BEFORE = """      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""

AFTER = """      // ══ 工事4c: スマホ幅で入力欄が 16px（iOS の自動ズーム対策）══
      .then(function () {
        // 幅を変えて @media を効かせるため、同じページを iframe に読み込んで測る
        function measure(width) {
          return new Promise(function (resolve) {
            var f = document.createElement('iframe');
            f.style.cssText = 'position:fixed;left:-9999px;top:0;height:800px;border:0';
            f.style.width = width + 'px';
            f.src = location.pathname;
            f.onload = function () {
              var d = f.contentDocument;
              var w = f.contentWindow;
              var size = function (sel) {
                var el = d.querySelector(sel);
                return el ? w.getComputedStyle(el).fontSize : '(要素が無い)';
              };
              var out = {
                date: size('#payDate'),
                memo: size('#payMemo'),
                amount: size('#payAmount'),
                payer: size('#payPayer'),
                groupName: size('#newGroupName')
              };
              // メンバー名の入力欄は ui.js が作るので、同じ形の要素を差し込んで測る
              var row = d.createElement('div');
              row.className = 'member-row';
              row.innerHTML = '<input class="form-input member-row-input" value="x">';
              (d.querySelector('#editMemberList') || d.body).appendChild(row);
              out.memberRow = w.getComputedStyle(row.querySelector('input')).fontSize;
              f.remove();
              resolve(out);
            };
            document.body.appendChild(f);
          });
        }

        return measure(390).then(function (m) {
          check('スマホ幅: 日付の入力欄が 16px', m.date === '16px', m.date);
          check('スマホ幅: メモの入力欄が 16px', m.memo === '16px', m.memo);
          check('スマホ幅: 金額の入力欄が 16px', m.amount === '16px', m.amount);
          check('スマホ幅: 支払った人の select が 16px', m.payer === '16px', m.payer);
          check('スマホ幅: グループ名の入力欄も 16px', m.groupName === '16px', m.groupName);
          check('スマホ幅: メンバー名の入力欄が 16px', m.memberRow === '16px', m.memberRow);
          return measure(1024);
        }).then(function (m) {
          check('PC 幅: 入力欄は 14.4px のまま（見た目を変えない）',
            m.date === '14.4px' && m.memo === '14.4px' && m.amount === '14.4px',
            m.date + ' / ' + m.memo + ' / ' + m.amount);
          check('PC 幅: メンバー名の入力欄も変えていない',
            m.memberRow === '14.08px', m.memberRow);
        });
      })

      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""


def main():
    with io.open(DRIVER, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "スマホ幅: 日付の入力欄が 16px" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1

    with io.open(DRIVER, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: " + DRIVER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
