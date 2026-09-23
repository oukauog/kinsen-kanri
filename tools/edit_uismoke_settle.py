# -*- coding: utf-8 -*-
"""
工事3: 画面の通し確認に清算まわりを足す。

  ・tests/ui_smoke_fakes.js  … 偽 KKStore に confirmSettlement / setTransferDone /
                               undoSettlement を足し、清算済みロックと pending を
                               本物（store.js）と同じふるまいにする
  ・tests/ui_smoke_driver.js … 確認中の登録と黄色表示、確認中があると確定ボタンが無効、
                               清算確定でグレー化と残高の変化、清算済みの編集拒否、
                               送金チェックの反映、取り消しで戻る、古い清算は取り消せない、
                               累計／未清算の切替

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_settle.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKES = os.path.join(ROOT, "tests", "ui_smoke_fakes.js")
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

FAKE_REPS = []

FAKE_REPS.append((
    "偽ストアの支払い追加で金額確認中を扱う",
    """      data.groups[code].payments[pid] = {
        date: p.date, memo: p.memo || '', payerId: p.payerId, amount: p.amount,
        participants: p.participants, settlementId: null, pending: false,
        createdBy: USER.uid, createdAt: Date.now(), updatedAt: Date.now()
      };""",
    """      var pending = p.pending === true;
      data.groups[code].payments[pid] = {
        date: p.date, memo: p.memo || '', payerId: p.payerId,
        amount: pending ? 0 : p.amount,
        participants: p.participants, settlementId: null, pending: pending,
        createdBy: USER.uid, createdAt: Date.now(), updatedAt: Date.now()
      };"""))

FAKE_REPS.append((
    "偽ストアの更新・削除に清算済みロックと pending を足す",
    """    updatePayment: function (code, pid, p) {
      var t = data.groups[code].payments[pid];
      t.date = p.date; t.memo = p.memo || ''; t.payerId = p.payerId;
      t.amount = p.amount; t.participants = p.participants; t.updatedAt = Date.now();
      notifyGroup(code); return Promise.resolve();
    },
    removePayment: function (code, pid) {
      delete data.groups[code].payments[pid]; notifyGroup(code); return Promise.resolve();
    },""",
    """    updatePayment: function (code, pid, p) {
      var t = data.groups[code].payments[pid];
      if (t && t.settlementId != null) return reportLocked('支払いを更新できませんでした');
      var pending = p.pending === true;
      t.date = p.date; t.memo = p.memo || ''; t.payerId = p.payerId;
      t.amount = pending ? 0 : p.amount; t.pending = pending;
      t.participants = p.participants; t.updatedAt = Date.now();
      notifyGroup(code); return Promise.resolve();
    },
    removePayment: function (code, pid) {
      var t = data.groups[code].payments[pid];
      if (t && t.settlementId != null) return reportLocked('支払いを削除できませんでした');
      delete data.groups[code].payments[pid]; notifyGroup(code); return Promise.resolve();
    },

    // ---- 清算（工事3）----
    confirmSettlement: function (code, settlement) {
      var sid = nextId('s');
      var g = data.groups[code];
      g.settlements = g.settlements || {};
      g.settlements[sid] = clone(settlement);
      Object.keys(settlement.paymentIds || {}).forEach(function (pid) {
        if (g.payments[pid]) g.payments[pid].settlementId = sid;
      });
      notifyGroup(code);
      return Promise.resolve(sid);
    },
    setTransferDone: function (code, sid, tid, done) {
      var t = data.groups[code].settlements[sid].transfers[tid];
      t.done = !!done;
      t.doneAt = done ? Date.now() : null;
      t.doneBy = done ? USER.uid : null;
      notifyGroup(code);
      return Promise.resolve();
    },
    undoSettlement: function (code, sid, paymentIds) {
      var g = data.groups[code];
      Object.keys(paymentIds || {}).forEach(function (pid) {
        if (g.payments[pid]) g.payments[pid].settlementId = null;
      });
      delete g.settlements[sid];
      notifyGroup(code);
      return Promise.resolve();
    },"""))

FAKE_REPS.append((
    "清算済みロックの通知を足す",
    """  // store.js の wrapWrite と同じふるまい: 通知して、印を付けて、拒否する
  function reportFail(op) {""",
    """  // store.js の ifNotSettled と同じふるまい（清算済みは書かずに拒否）
  function reportLocked(op) {
    var err = new Error('清算済みの支払いは編集できません。先に清算を取り消してください');
    err.code = 'KK_SETTLED_LOCKED';
    err.__kkReported = true;
    if (writeErrCb) writeErrCb(op, err);
    return Promise.reject(err);
  }

  // store.js の wrapWrite と同じふるまい: 通知して、印を付けて、拒否する
  function reportFail(op) {"""))


DRIVER_REPS = []

DRIVER_REPS.append((
    "清算まわりの確認を足す",
    """        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);""",
    """        return wait(20);
      })

      // ══ 工事3: 金額確認中・清算の記録・取り消し ══
      .then(function () {
        root.KKStore._seedGroup('SETL01', 'テスト清算', ['P', 'Q', 'R']);
        return root.KKStore.joinGroup('SETL01').then(function () { return wait(80); });
      })
      .then(function () {
        root.selectGroup('SETL01');
        return wait(80);
      })
      .then(function () {
        // P が 3000 円（3 人）→ 残高 +2000 / -1000 / -1000
        root.openPaymentModal();
        $('payMemo').value = 'テスト宿代';
        $('payAmount').value = '3000';
        root.recordPayment();
        return wait(80);
      })
      .then(function () {
        // 金額確認中の支払いを 1 件足す
        root.openPaymentModal();
        check('金額確認中のチェックは既定で外れている', $('payPending').checked === false);
        $('payMemo').value = 'テスト確認中のおみやげ';
        $('payPending').checked = true;
        root.onPendingToggle();
        check('確認中にすると金額欄のプレースホルダが変わる',
          $('payAmount').placeholder === 'あとで入力', $('payAmount').placeholder);
        root.recordPayment();
        return wait(80);
      })
      .then(function () {
        check('金額を空のまま確認中で登録できる',
          $('main').textContent.indexOf('テスト確認中のおみやげ') >= 0);
        var row = Array.prototype.filter.call($('main').querySelectorAll('.payment-item'),
          function (el) { return el.textContent.indexOf('確認中のおみやげ') >= 0; })[0];
        check('確認中の行が薄黄色（pending）になる',
          !!row && row.classList.contains('pending'), row ? row.className : '(行が無い)');
        check('確認中の行の金額欄に「確認中」と出る',
          !!row && row.querySelector('.payment-total').textContent === '確認中',
          row ? row.querySelector('.payment-total').textContent : '');
        check('確認中の注記が残高の見出しに出る',
          $('main').textContent.indexOf('金額確認中 1 件') >= 0);
        check('確認中は残高に入らない（+¥2,000 のまま）',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,000') >= 0,
          $('main').querySelector('.balance-grid').textContent);

        // 清算モーダル: 警告と確定ボタン無効
        root.openSettlement();
        return wait(60);
      })
      .then(function () {
        check('清算モーダルが開く', isOpen('settlementModal'));
        check('確認中があると黄色の警告が出る',
          !!$('settlementContent').querySelector('.settle-warn') &&
          $('settlementContent').textContent.indexOf('金額確認中の支払いが 1 件') >= 0);
        check('確認中のメモが警告の一覧に出る',
          $('settlementContent').textContent.indexOf('確認中のおみやげ') >= 0);
        check('確認中があると「この内容で清算する」が無効',
          !!$('settleConfirmBtn') && $('settleConfirmBtn').disabled === true);
        check('確認中でも暫定の送金リストは見られる',
          $('settlementContent').querySelectorAll('.settlement-item').length === 2);
        root.closeModal('settlementModal');

        // 金額を入れて確認中を外す
        var pays = root.KKStore._data.groups.SETL01.payments;
        var pid = Object.keys(pays).filter(function (k) { return pays[k].pending; })[0];
        root.openEditPayModal(pid);
        return wait(40);
      })
      .then(function () {
        check('編集モーダルに確認中のチェックが入って開く', $('payPending').checked === true);
        $('payPending').checked = false;
        root.onPendingToggle();
        $('payAmount').value = '600';
        root.recordPayment();
        return wait(80);
      })
      .then(function () {
        check('金額を入れて確認中を外すと通常の支払いに戻る',
          $('main').querySelectorAll('.payment-item.pending').length === 0);
        check('確認中の注記が消える', $('main').textContent.indexOf('金額確認中') < 0);
        root.openSettlement();
        return wait(60);
      })
      .then(function () {
        check('確認中が無くなると確定ボタンが有効になる',
          !!$('settleConfirmBtn') && $('settleConfirmBtn').disabled === false);
        check('対象件数と送金本数が出る',
          $('settlementContent').textContent.indexOf('対象の支払い 2 件') >= 0 &&
          $('settlementContent').textContent.indexOf('送金 2 本') >= 0,
          $('settlementContent').textContent);
        root.doConfirmSettlement();
        return wait(150);
      })
      .then(function () {
        var g = root.KKStore._data.groups.SETL01;
        var sids = Object.keys(g.settlements || {});
        check('清算レコードが 1 件できる', sids.length === 1, 'sids=' + sids.length);
        check('対象の支払いすべてに settlementId が入る',
          Object.keys(g.payments).every(function (pid) { return g.payments[pid].settlementId === sids[0]; }));
        check('過去の清算に日時と対象件数が出る',
          $('settlementContent').textContent.indexOf('対象 2 件') >= 0,
          $('settlementContent').textContent);
        root.closeModal('settlementModal');
        return wait(60);
      })
      .then(function () {
        check('清算後の履歴がグレー（settled）になる',
          $('main').querySelectorAll('.payment-item.settled').length === 2);
        check('清算済みバッジが出る',
          $('main').textContent.indexOf('清算済み') >= 0);
        check('清算後の未清算残高が 0 になる',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,000') < 0 &&
          $('main').querySelector('.balance-grid').textContent.indexOf('ほぼ均等') >= 0,
          $('main').querySelector('.balance-grid').textContent);

        // 累計に切り替えると清算済みも含めて計算する
        root.setBalanceMode('all');
        return wait(40);
      })
      .then(function () {
        check('累計に切り替えると清算済みも計算に入る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,200') >= 0,
          $('main').querySelector('.balance-grid').textContent);
        check('見出しが「累計」になる', $('main').textContent.indexOf('残高 — 累計') >= 0);
        root.setBalanceMode('unsettled');
        return wait(40);
      })
      .then(function () {
        check('未清算のみに戻せる', $('main').textContent.indexOf('残高 — 未清算分') >= 0);

        // 清算済みの編集はデータ層でも止まる
        var pid = Object.keys(root.KKStore._data.groups.SETL01.payments)[0];
        return root.KKStore.updatePayment('SETL01', pid, {
          date: '2026-09-30', memo: '書き換え', payerId: 'x', amount: 1, participants: {}
        }).then(function () {
          check('清算済みの支払いは更新できない（データ層で拒否）', false, '更新が通ってしまった');
        }, function () {
          return wait(40);
        });
      })
      .then(function () {
        var toasts = document.querySelectorAll('.toast-box .toast.toast-error');
        var last = toasts[toasts.length - 1];
        check('清算済みの支払いは更新できない（データ層で拒否）',
          !!last && last.textContent.indexOf('清算済みの支払いは編集できません') >= 0,
          last ? last.textContent : '(トーストが出ていない)');

        // 追加 1 件 → 再清算は追加分だけ
        root.openPaymentModal();
        $('payMemo').value = 'テスト清算後の追加';
        $('payAmount').value = '900';
        root.recordPayment();
        return wait(100);
      })
      .then(function () {
        root.openSettlement();
        return wait(60);
      })
      .then(function () {
        check('再清算の対象は追加した 1 件だけ',
          $('settlementContent').textContent.indexOf('対象の支払い 1 件') >= 0,
          $('settlementContent').textContent);

        // 送金チェック（他端末にも届く道＝ストア経由）
        var g = root.KKStore._data.groups.SETL01;
        var sid = Object.keys(g.settlements)[0];
        var tid = Object.keys(g.settlements[sid].transfers)[0];
        root.toggleTransferDone(sid, tid, true);
        return wait(100);
      })
      .then(function () {
        var g = root.KKStore._data.groups.SETL01;
        var sid = Object.keys(g.settlements)[0];
        var tid = Object.keys(g.settlements[sid].transfers)[0];
        check('送金チェックがデータに入る', g.settlements[sid].transfers[tid].done === true);
        check('送金チェックが画面（清算モーダル）に反映される',
          $('settlementContent').querySelectorAll('.transfer-row.done').length === 1,
          'done 行 = ' + $('settlementContent').querySelectorAll('.transfer-row.done').length);
        check('全部チェックしないと完了バッジは出ない',
          $('settlementContent').querySelectorAll('.past-done-badge').length === 0);
        root.toggleTransferDone(sid, Object.keys(g.settlements[sid].transfers)[1], true);
        return wait(100);
      })
      .then(function () {
        check('全部チェックすると完了バッジが出る',
          $('settlementContent').querySelectorAll('.past-done-badge').length === 1);

        // 取り消し（チェックが入っているので確認ダイアログは強い文言）
        var sid = Object.keys(root.KKStore._data.groups.SETL01.settlements)[0];
        root.doUndoSettlement(sid);
        return wait(150);
      })
      .then(function () {
        var g = root.KKStore._data.groups.SETL01;
        check('取り消すと清算レコードが消える',
          Object.keys(g.settlements || {}).length === 0);
        check('取り消すと支払いが未清算に戻る',
          Object.keys(g.payments).every(function (pid) { return g.payments[pid].settlementId == null; }));
        root.closeModal('settlementModal');
        return wait(60);
      })
      .then(function () {
        check('取り消すと履歴のグレーが消える',
          $('main').querySelectorAll('.payment-item.settled').length === 0);
        check('取り消すと残高が元に戻る',
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,300') >= 0,
          $('main').querySelector('.balance-grid').textContent);

        // 古い清算は取り消せない（2 回清算してから確かめる）
        root.openSettlement();
        return wait(60);
      })
      .then(function () { root.doConfirmSettlement(); return wait(150); })
      .then(function () {
        root.closeModal('settlementModal');
        root.openPaymentModal();
        $('payMemo').value = 'テスト2回目の支払い';
        $('payAmount').value = '1200';
        root.recordPayment();
        return wait(100);
      })
      .then(function () { root.openSettlement(); return wait(60); })
      .then(function () { root.doConfirmSettlement(); return wait(150); })
      .then(function () {
        var g = root.KKStore._data.groups.SETL01;
        check('清算レコードが 2 件になる', Object.keys(g.settlements).length === 2,
          Object.keys(g.settlements).length + ' 件');
        check('取り消しボタンは最新の 1 件だけに出る',
          $('settlementContent').querySelectorAll('.past-settlement').length === 2 &&
          $('settlementContent').textContent.indexOf('取り消せるのは最新の清算のみです') >= 0);

        // 古い方を直接取り消そうとしても拒否される
        var sids = Object.keys(g.settlements);
        var oldest = sids.sort(function (a, b) {
          return g.settlements[a].createdAt - g.settlements[b].createdAt;
        })[0];
        root.doUndoSettlement(oldest);
        return wait(100);
      })
      .then(function () {
        var g = root.KKStore._data.groups.SETL01;
        check('古い清算は取り消せない（レコードが残る）',
          Object.keys(g.settlements).length === 2);
        var toasts = document.querySelectorAll('.toast-box .toast.toast-error');
        var last = toasts[toasts.length - 1];
        check('古い清算を取り消そうとすると理由が出る',
          !!last && last.textContent.indexOf('最新の清算のみ') >= 0,
          last ? last.textContent : '(トーストが出ていない)');
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
    if "confirmSettlement" in io.open(FAKES, encoding="utf-8").read():
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
