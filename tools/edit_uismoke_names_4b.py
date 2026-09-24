# -*- coding: utf-8 -*-
"""
工事4b-B: 画面の通し確認に「誰が入力したか・誰がチェックしたか」の確認を足す。

  ・偽ストア（ui_smoke_fakes.js）を本物と同じく名前つきで保存するようにする
  ・名前の無い古い支払いを仕込めるようにする（_seedOldPayment）
  ・ドライバに確認を足す（入力者が出る / 名前が無ければ出ない / 確定者 / チェック者）

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_names_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKES = os.path.join(ROOT, "tests", "ui_smoke_fakes.js")
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

FAKE_REPS = []

FAKE_REPS.append((
    "偽ストアに表示名の関数を足す",
    """  root.KKStore = {
    _data: data,
    localId: function () { return nextId('m'); },""",
    """  root.KKStore = {
    _data: data,
    // 本物の store.js と同じ決め方（displayName → メールの @ 前 → （名前なし））
    currentUserName: function () {
      return (USER.displayName || '').trim() ||
        ((USER.email || '').indexOf('@') > 0 ? USER.email.split('@')[0] : '（名前なし）');
    },
    localId: function () { return nextId('m'); },"""))

FAKE_REPS.append((
    "偽ストアの支払い追加に入力者の名前を足す",
    """        date: p.date, memo: p.memo || '', payerId: p.payerId,
        amount: pending ? 0 : p.amount,
        participants: p.participants, settlementId: null, pending: pending,
        createdBy: USER.uid, createdAt: Date.now(), updatedAt: Date.now()
      };""",
    """        date: p.date, memo: p.memo || '', payerId: p.payerId,
        amount: pending ? 0 : p.amount,
        participants: p.participants, settlementId: null, pending: pending,
        createdBy: USER.uid, createdByName: root.KKStore.currentUserName(),
        createdAt: Date.now(), updatedAt: Date.now()
      };"""))

FAKE_REPS.append((
    "偽ストアの清算確定に確定者の名前を足す",
    """      g.settlements[sid] = clone(settlement);""",
    """      g.settlements[sid] = clone(settlement);
      g.settlements[sid].createdByName = root.KKStore.currentUserName();"""))

FAKE_REPS.append((
    "偽ストアの送金チェックにチェック者の名前を足す",
    """      t.doneAt = done ? Date.now() : null;
      t.doneBy = done ? USER.uid : null;""",
    """      t.doneAt = done ? Date.now() : null;
      t.doneBy = done ? USER.uid : null;
      t.doneByName = done ? root.KKStore.currentUserName() : null;"""))

FAKE_REPS.append((
    "確認用に、名前の無い古い支払いを仕込めるようにする",
    """    _setConnected: function (ok) { if (connCb) connCb(ok); },""",
    """    // 工事4b 以前に入った支払い（createdByName が無い）を仕込む確認用
    _seedOldPayment: function (code, p) {
      var pid = nextId('p');
      data.groups[code].payments = data.groups[code].payments || {};
      data.groups[code].payments[pid] = {
        date: p.date, memo: p.memo, payerId: p.payerId, amount: p.amount,
        participants: p.participants, settlementId: null, pending: false,
        createdBy: 'someone-else', createdAt: Date.now(), updatedAt: Date.now()
      };
      notifyGroup(code);
      return pid;
    },
    _setConnected: function (ok) { if (connCb) connCb(ok); },"""))


DRIVER_REPS = []

DRIVER_REPS.append((
    "入力者・確定者・チェック者の確認を足す",
    """      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);""",
    """      // ══ 工事4b-B: 誰が入力したか・誰がチェックしたか ══
      .then(function () {
        root.KKStore._seedGroup('NAME01', 'テスト入力者', ['さ', 'し']);
        return root.KKStore.joinGroup('NAME01').then(function () { return wait(80); });
      })
      .then(function () {
        root.selectGroup('NAME01');
        return wait(80);
      })
      .then(function () {
        root.openPaymentModal();
        $('payMemo').value = 'テスト新しい支払い';
        $('payAmount').value = '2000';
        root.recordPayment();
        return wait(100);
      })
      .then(function () {
        var row = Array.prototype.filter.call($('main').querySelectorAll('.payment-item'),
          function (el) { return el.textContent.indexOf('テスト新しい支払い') >= 0; })[0];
        check('新しい支払いに入力者が出る',
          !!row && row.textContent.indexOf('入力: テスト太郎') >= 0,
          row ? row.textContent : '(行が無い)');

        // 工事4b 以前の支払い（createdByName が無い）を仕込む
        root.KKStore._seedOldPayment('NAME01', {
          date: '2026-08-01', memo: 'テスト古い支払い',
          payerId: Object.keys(root.KKStore._data.groups.NAME01.members)[0],
          amount: 1000,
          participants: (function () {
            var o = {};
            Object.keys(root.KKStore._data.groups.NAME01.members).forEach(function (m) { o[m] = true; });
            return o;
          })()
        });
        return wait(100);
      })
      .then(function () {
        var oldRow = Array.prototype.filter.call($('main').querySelectorAll('.payment-item'),
          function (el) { return el.textContent.indexOf('テスト古い支払い') >= 0; })[0];
        check('名前が無い支払いには「入力:」を出さない',
          !!oldRow && oldRow.textContent.indexOf('入力:') < 0,
          oldRow ? oldRow.textContent : '(行が無い)');
        check('名前が無くても「不明」等の文字を出さない',
          !!oldRow && oldRow.textContent.indexOf('不明') < 0);

        root.openSettlement();
        return wait(60);
      })
      .then(function () { root.doConfirmSettlement(); return wait(150); })
      .then(function () {
        check('過去の清算の見出しに確定した人が出る',
          $('settlementContent').textContent.indexOf('テスト太郎 が確定') >= 0,
          $('settlementContent').textContent.slice(0, 160));

        var g = root.KKStore._data.groups.NAME01;
        var sid = Object.keys(g.settlements)[0];
        var tid = Object.keys(g.settlements[sid].transfers)[0];
        check('チェック前はチェック者の表示が出ていない',
          $('settlementContent').querySelectorAll('.transfer-by').length === 0);
        root.toggleTransferDone(sid, tid, true);
        return wait(120);
      })
      .then(function () {
        var by = $('settlementContent').querySelector('.transfer-by');
        check('送金チェックにチェックした人と日時が出る',
          !!by && by.textContent.indexOf('テスト太郎') >= 0 &&
          /\\d{2}\\/\\d{2} \\d{2}:\\d{2}/.test(by.textContent),
          by ? by.textContent : '(表示が無い)');
        root.closeModal('settlementModal');
        return wait(40);
      })

      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""))


def apply(path, reps):
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors, plan = [], []
    for label, before, after in reps:
        b = fix(before)
        n = src.count(b)
        if n != 1:
            errors.append("%s: 一致 %d 件（1 件であるべき）" % (label, n))
        plan.append((label, b, fix(after)))
    if errors:
        print("中止しました（%s）。ファイルは変更していません:" % os.path.basename(path))
        for e in errors:
            print("  - " + e)
        return False

    out = src
    for label, b, a in plan:
        out = out.replace(b, a, 1)
        print("置換しました: " + label)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + path)
    return True


def main():
    if "_seedOldPayment" in io.open(FAKES, encoding="utf-8").read():
        print("すでに適用済みです。何もしません。")
        return 0
    if not apply(FAKES, FAKE_REPS):
        return 1
    if not apply(DRIVER, DRIVER_REPS):
        print("※ fakes だけ適用されました。driver の一致を直して再実行してください")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
