# -*- coding: utf-8 -*-
"""
工事2: 画面の通し確認に、旧ルームからの取り込み・オフラインの帯・
書き込み失敗のトーストを足す。

  ・tests/ui_smoke_fakes.js  … 偽 KKStore に readRoom / allocCodes / migrateRoom /
                               onWriteError と、テスト用の仕掛け（オフライン切替、
                               次の書き込みをわざと失敗させる）を足す
  ・tests/ui_smoke_driver.js … 上を使う確認項目を足す

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_migrate.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKES = os.path.join(ROOT, "tests", "ui_smoke_fakes.js")
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

FAKE_REPS = []

FAKE_REPS.append((
    "偽ストアに状態を足す",
    """  var data = { users: {}, groups: {} };
  var watchers = { myGroups: null, group: {}, meta: {} };""",
    """  var data = { users: {}, groups: {} };
  var rooms = {};                 // 旧バージョンのルーム（工事2 の移行確認用）
  var connCb = null;              // watchConnection のコールバック
  var writeErrCb = null;          // onWriteError のコールバック
  var failNext = false;           // 次の書き込みをわざと失敗させる
  var watchers = { myGroups: null, group: {}, meta: {} };"""))

FAKE_REPS.append((
    "書き込み失敗の通し道を足す",
    """  var id = 0;
  function nextId(p) { id++; return p + id; }""",
    """  var id = 0;
  function nextId(p) { id++; return p + id; }

  // store.js の wrapWrite と同じふるまい: 通知して、印を付けて、拒否する
  function reportFail(op) {
    var err = new Error('テストのための失敗');
    err.code = 'PERMISSION_DENIED';
    err.__kkReported = true;
    if (writeErrCb) writeErrCb(op, err);
    return Promise.reject(err);
  }"""))

FAKE_REPS.append((
    "支払い追加をわざと失敗させられるようにする",
    """    addPayment: function (code, p) {
      var pid = nextId('p');""",
    """    addPayment: function (code, p) {
      if (failNext) { failNext = false; return reportFail('支払いを記録できませんでした'); }
      var pid = nextId('p');"""))

FAKE_REPS.append((
    "移行まわりと確認用の仕掛けを足す",
    """    watchConnection: function (cb) { later(function () { cb(true); }); },""",
    """    watchConnection: function (cb) { connCb = cb; later(function () { cb(true); }); },
    onWriteError: function (fn) { writeErrCb = fn; },

    // ---- 旧バージョンからの取り込み（工事2）----
    readRoom: function (code) {
      return Promise.resolve(rooms[code] ? clone(rooms[code]) : null);
    },
    allocCodes: function (n) {
      var out = [];
      for (var i = 0; i < n; i++) { id++; out.push('NEWC' + (10 + id)); }
      return Promise.resolve(out);
    },
    migrateRoom: function (conv) {
      if (failNext) { failNext = false; return reportFail('取り込みに失敗しました'); }
      var migrated = [], already = [];
      var codes = (conv && conv.order) ? conv.order : [];
      codes.forEach(function (code) {
        var g = conv.groups[code];
        data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
        data.users[USER.uid].groups[code] = { joinedAt: Date.now() };
        if (data.groups[code] && data.groups[code].meta) { already.push(code); return; }
        data.groups[code] = {
          meta: clone(g.meta), members: clone(g.members), payments: clone(g.payments)
        };
        migrated.push(code);
      });
      notifyMyGroups();
      codes.forEach(notifyGroup);
      return Promise.resolve({ migrated: migrated, already: already });
    },"""))

FAKE_REPS.append((
    "確認用の操作（オフライン切替・旧ルームの仕込み）を足す",
    """    _seedGroup: function (code, name, memberNames) {""",
    """    _setConnected: function (ok) { if (connCb) connCb(ok); },
    _failNextWrite: function () { failNext = true; },
    _seedRoom: function (code, room) { rooms[code] = room; },
    _seedGroup: function (code, name, memberNames) {"""))


DRIVER_REPS = []

DRIVER_REPS.append((
    "取り込み・オフライン・書き込み失敗の確認を足す",
    """        check('ログアウトでログイン画面に戻る',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);""",
    """        check('ログアウトでログイン画面に戻る',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);
        root.KKAuth._signIn();
        return wait(40);
      })

      // ── オフラインの帯（§5.7）──
      .then(function () {
        check('つながっているときは帯が出ていない', $('offlineBanner').hidden === true);
        root.KKStore._setConnected(false);
        return wait(20);
      })
      .then(function () {
        check('オフラインになると帯が出る',
          $('offlineBanner').hidden === false &&
          $('offlineBanner').textContent.indexOf('オフライン') >= 0);
        check('オフラインで接続ドットが灰色になる',
          $('connDot').className.indexOf('off') >= 0);
        root.KKStore._setConnected(true);
        return wait(20);
      })
      .then(function () {
        check('つながり直すと帯が消える', $('offlineBanner').hidden === true);
        check('つながり直すと接続ドットが戻る', $('connDot').className.indexOf('off') < 0);

        // ── 書き込みが失敗したらトーストで知らせる（§5.7）──
        root.KKStore._seedGroup('FAIL01', 'テスト失敗確認', ['ら', 'り']);
        return root.KKStore.joinGroup('FAIL01').then(function () { return wait(60); });
      })
      .then(function () {
        root.selectGroup('FAIL01');
        return wait(60);
      })
      .then(function () {
        root.KKStore._failNextWrite();
        root.openPaymentModal();
        $('payMemo').value = '失敗するはずの支払い';
        $('payAmount').value = '1000';
        root.recordPayment();
        return wait(80);
      })
      .then(function () {
        var toasts = document.querySelectorAll('.toast-box .toast.toast-error');
        var last = toasts[toasts.length - 1];
        check('書き込みが失敗すると赤いトーストで理由が出る',
          !!last && last.textContent.indexOf('支払いを記録できませんでした') >= 0 &&
          last.textContent.indexOf('権限がありません') >= 0,
          last ? last.textContent : '(トーストが出ていない)');
        check('失敗した支払いは履歴に入らない',
          $('main').textContent.indexOf('失敗するはずの支払い') < 0);

        // ── 旧バージョンからの取り込み（工事2）──
        root.KKStore._seedRoom('TESTMG', {
          groups: [
            { id: 'gA', name: 'テスト移行A', members: [{ id: 'a1', name: 'あ' }, { id: 'a2', name: 'い' }, { id: 'a3', name: 'う' }] },
            { id: 'gB', name: 'テスト移行B', members: [{ id: 'b1', name: 'か' }, { id: 'b2', name: 'き' }] },
            { id: 'gDel', name: 'テスト消した会', members: [{ id: 'd1', name: 'さ' }] }
          ],
          payments: [
            { id: 'pa1', groupId: 'gA', date: '2026-08-01', memo: 'テスト宿', payerId: 'a1', amount: 30000, participants: ['a1', 'a2', 'a3'] },
            { id: 'pa2', groupId: 'gA', date: '2026-08-02', memo: 'テスト昼食', payerId: 'a2', amount: 4500, participants: ['a1', 'a2'] },
            { id: 'pa3-del', groupId: 'gA', date: '2026-08-03', memo: 'テスト取り消し', payerId: 'a1', amount: 9999, participants: ['a1', 'a2', 'a3'] },
            { id: 'pb1', groupId: 'gB', date: '2026-09-01', memo: 'テスト飲み会', payerId: 'b1', amount: 8000, participants: ['b1', 'b2'] },
            { id: 'porphan', groupId: 'gNowhere', date: '2026-09-02', memo: 'テスト孤児', payerId: 'x', amount: 100, participants: ['x'] }
          ],
          deletedGroupIds: ['gDel'],
          deletedPaymentIds: ['pa3-del']
        });
        root.openJoinModal();
        $('joinCodeInput').value = 'TESTMG';
        root.doJoin();
        return wait(150);
      })
      .then(function () {
        check('旧ルームが見つかると取り込みの選択ダイアログが開く',
          isOpen('migrateModal') && !isOpen('joinGroupModal'));
        check('取り込めるグループだけが選択肢に出る（削除済みは出ない）',
          $('migrateContent').querySelectorAll('input[name="migratePick"]').length === 2 &&
          $('migrateContent').textContent.indexOf('テスト消した会') < 0,
          $('migrateContent').textContent);
        check('選択肢にメンバー数と支払い件数が出る',
          $('migrateContent').textContent.indexOf('メンバー 3 人') >= 0 &&
          $('migrateContent').textContent.indexOf('支払い 2 件') >= 0,
          $('migrateContent').textContent);
        check('除外する件数が説明に出る',
          $('migrateContent').textContent.indexOf('削除済みの支払い 1 件') >= 0 &&
          $('migrateContent').textContent.indexOf('グループが分からない支払い 1 件') >= 0);

        // 2 番目（テスト移行B）にコードを引き継がせる
        var radios = $('migrateContent').querySelectorAll('input[name="migratePick"]');
        radios[1].checked = true;
        root.confirmMigrate();
        return wait(250);
      })
      .then(function () {
        check('取り込み結果のダイアログが出る', isOpen('migrateResultModal'));
        var t = $('migrateResultContent').textContent;
        check('結果に両方のグループ名が出る',
          t.indexOf('テスト移行A') >= 0 && t.indexOf('テスト移行B') >= 0, t);
        check('選んだグループが元のコードを引き継ぐ',
          t.indexOf('TESTMG') >= 0 && root.KKStore._data.groups.TESTMG.meta.name === 'テスト移行B',
          root.KKStore._data.groups.TESTMG ? root.KKStore._data.groups.TESTMG.meta.name : '(無い)');
        check('もう一方には新しいコードが発行される',
          $('migrateResultContent').querySelectorAll('.migrate-result-code').length === 2, t);
        check('取り込んだ支払いの件数が正しい（削除済み・孤児を除く）',
          Object.keys(root.KKStore._data.groups.TESTMG.payments).length === 1,
          'TESTMG=' + Object.keys(root.KKStore._data.groups.TESTMG.payments).length);
        check('meta に移行元が記録される',
          root.KKStore._data.groups.TESTMG.meta.migratedFrom === 'rooms/TESTMG',
          root.KKStore._data.groups.TESTMG.meta.migratedFrom);
        root.closeMigrateResult();
        return wait(120);
      })
      .then(function () {
        check('閉じると取り込んだグループが開く',
          $('main').textContent.indexOf('テスト移行B') >= 0, $('main').textContent.slice(0, 80));
        check('取り込んだ支払いが履歴に出る',
          $('main').textContent.indexOf('テスト飲み会') >= 0 &&
          $('main').textContent.indexOf('8,000') >= 0);
        check('もう一方のグループもサイドバーに並ぶ',
          $('groupList').textContent.indexOf('テスト移行A') >= 0, $('groupList').textContent);

        // ── 2 回目は移行が走らない（通常参加になる）──
        return root.KKStore.leaveGroup('TESTMG').then(function () { return wait(120); });
      })
      .then(function () {
        root.openJoinModal();
        $('joinCodeInput').value = 'TESTMG';
        root.doJoin();
        return wait(200);
      })
      .then(function () {
        check('2 回目のコード参加では移行ダイアログが出ない', !isOpen('migrateModal'));
        check('2 回目は通常参加になる（グループが開く）',
          $('main').textContent.indexOf('テスト移行B') >= 0);
        check('2 回目の参加で中身が増えない（二重取り込みが無い）',
          Object.keys(root.KKStore._data.groups.TESTMG.payments).length === 1,
          'payments=' + Object.keys(root.KKStore._data.groups.TESTMG.payments).length);

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
    if "_setConnected" in io.open(FAKES, encoding="utf-8").read():
        print("すでに適用済みです。何もしません。")
        return 0
    # どちらか片方だけ適用されないよう、先に両方の一致を確かめてから書く
    ok = apply(FAKES, FAKE_REPS)
    if not ok:
        return 1
    if not apply(DRIVER, DRIVER_REPS):
        print("※ fakes だけ適用されました。driver の一致を直して再実行してください")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
