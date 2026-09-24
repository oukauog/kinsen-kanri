# -*- coding: utf-8 -*-
"""
工事4b-C: 画面の通し確認に「過去の清算の件数制限」の確認を足す。
あわせて css に「もっと見る」ボタンのスタイルを足す。

  ・清算 4 件なら全部出てボタンは出ない
  ・清算 6 件なら 5 件だけ出て「もっと見る（残り 1 件）」が出る
  ・押すと 6 件すべて出る／ボタンは消える
  ・開き直すと 5 件に戻る（保存しない）
  ・折りたたんでいても最新の清算（取り消しボタン）は出る

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_pastlimit_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")
CSS = os.path.join(ROOT, "css", "v2.css")

CSS_BEFORE = """.transfer-row.done .transfer-by { text-decoration: none; }"""
CSS_AFTER = """.transfer-row.done .transfer-by { text-decoration: none; }
.past-more { margin-top: 4px; width: 100%; }"""

DRIVER_BEFORE = """      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""

DRIVER_AFTER = """      // ══ 工事4b-C: 過去の清算の件数制限 ══
      .then(function () {
        root.KKStore._seedGroup('MANY01', 'テスト清算たくさん', ['な', 'に']);
        return root.KKStore.joinGroup('MANY01').then(function () { return wait(80); });
      })
      .then(function () {
        root.selectGroup('MANY01');
        return wait(80);
      })
      .then(function () {
        // 「支払い 1 件 → 清算」をくり返して清算レコードを増やす
        var mids = Object.keys(root.KKStore._data.groups.MANY01.members);
        var parts = {}; mids.forEach(function (m) { parts[m] = true; });
        var addAndSettle = function (i, memo, offset) {
          return root.KKStore.addPayment('MANY01', {
            date: '2026-09-01', memo: memo, payerId: mids[0],
            amount: 1000 * (i + 1), participants: parts
          }).then(function () { return wait(40); }).then(function () {
            var s = root.Settle.buildSettlement(
              root.Calc.normalizeMembers(root.KKStore._data.groups.MANY01.members),
              root.KKStore._data.groups.MANY01.payments,
              { uid: 'u-test', now: Date.now() + offset });
            return root.KKStore.confirmSettlement('MANY01', s);
          }).then(function () { return wait(40); });
        };
        var step = function (i) {
          if (i >= 4) return Promise.resolve();
          return addAndSettle(i, 'テスト清算用' + (i + 1), i * 1000)
            .then(function () { return step(i + 1); });
        };
        return step(0);
      })
      .then(function () {
        root.openSettlement();
        return wait(80);
      })
      .then(function () {
        check('清算が 4 件できている',
          Object.keys(root.KKStore._data.groups.MANY01.settlements).length === 4,
          Object.keys(root.KKStore._data.groups.MANY01.settlements).length + ' 件');
        check('4 件なら全部出て「もっと見る」は出ない',
          $('settlementContent').querySelectorAll('.past-settlement').length === 4 &&
          !$('pastMoreBtn'),
          $('settlementContent').querySelectorAll('.past-settlement').length + ' 件');
        root.closeModal('settlementModal');

        // さらに 2 件足して 6 件にする
        var mids = Object.keys(root.KKStore._data.groups.MANY01.members);
        var parts = {}; mids.forEach(function (m) { parts[m] = true; });
        var step = function (i) {
          if (i >= 2) return Promise.resolve();
          return root.KKStore.addPayment('MANY01', {
            date: '2026-09-1' + i, memo: 'テスト追加' + i,
            payerId: mids[0], amount: 500, participants: parts
          }).then(function () { return wait(40); }).then(function () {
            var s = root.Settle.buildSettlement(
              root.Calc.normalizeMembers(root.KKStore._data.groups.MANY01.members),
              root.KKStore._data.groups.MANY01.payments,
              { uid: 'u-test', now: Date.now() + 10000 + i * 1000 });
            return root.KKStore.confirmSettlement('MANY01', s);
          }).then(function () { return wait(40); }).then(function () { return step(i + 1); });
        };
        return step(0);
      })
      .then(function () {
        root.openSettlement();
        return wait(80);
      })
      .then(function () {
        check('清算が 6 件になる',
          Object.keys(root.KKStore._data.groups.MANY01.settlements).length === 6,
          Object.keys(root.KKStore._data.groups.MANY01.settlements).length + ' 件');
        check('6 件あると 5 件だけ出る',
          $('settlementContent').querySelectorAll('.past-settlement').length === 5,
          $('settlementContent').querySelectorAll('.past-settlement').length + ' 件');
        check('「もっと見る（残り 1 件）」が出る',
          !!$('pastMoreBtn') && $('pastMoreBtn').textContent.indexOf('残り 1 件') >= 0,
          $('pastMoreBtn') ? $('pastMoreBtn').textContent : '(ボタンが無い)');
        check('折りたたんでいても最新の清算は出る（取り消しボタンがある）',
          $('settlementContent').textContent.indexOf('この清算を取り消す') >= 0);
        root.showAllPastSettlements();
        return wait(60);
      })
      .then(function () {
        check('「もっと見る」を押すと 6 件すべて出る',
          $('settlementContent').querySelectorAll('.past-settlement').length === 6,
          $('settlementContent').querySelectorAll('.past-settlement').length + ' 件');
        check('全件出したらボタンは消える', !$('pastMoreBtn'));
        root.closeModal('settlementModal');
        root.openSettlement();
        return wait(60);
      })
      .then(function () {
        check('開き直すと 5 件に戻る（展開状態は保存しない）',
          $('settlementContent').querySelectorAll('.past-settlement').length === 5 &&
          !!$('pastMoreBtn'));
        root.closeModal('settlementModal');
        return wait(40);
      })

      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""


def apply_one(path, before, after, label, guard):
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if guard in src:
        print("すでに適用済み（%s）。何もしません。" % os.path.basename(path))
        return True

    b, a = fix(before), fix(after)
    n = src.count(b)
    if n != 1:
        print("中止しました（%s: 一致 %d 件、1 件であるべき）。ファイルは変更していません。"
              % (label, n))
        return False

    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(b, a, 1))
    print("置換しました: " + label)
    return True


def main():
    if not apply_one(CSS, CSS_BEFORE, CSS_AFTER, "もっと見るのスタイル", ".past-more"):
        return 1
    if not apply_one(DRIVER, DRIVER_BEFORE, DRIVER_AFTER, "件数制限の確認", "pastMoreBtn"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
