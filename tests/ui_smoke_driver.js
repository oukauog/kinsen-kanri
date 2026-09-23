/*
 * tests/ui_smoke_driver.js — 画面の通し確認（ヘッドレスブラウザ用）
 *
 * tests/ui_smoke_fakes.js で Firebase を差し替えた状態で、
 * ログイン → グループ作成 → 支払い追加・編集・削除 → 清算表示 →
 * 設定（名前変更・メンバー追加・共有コード）→ コードで参加 → 退出
 * までを実際の DOM 操作で走らせ、結果を /__diag?... に投げる。
 *
 * 目的は「押しても動かない」「描画で例外」を無人で見つけること。
 * 金額の正しさは tests/calc.test.js 側で見ている。
 */
(function (root) {
  'use strict';

  var results = [];
  function beacon(msg) { try { fetch('/__diag?' + encodeURIComponent(msg)); } catch (e) { /* noop */ } }
  function check(name, cond, extra) {
    results.push((cond ? 'ok   ' : 'FAIL ') + name + (cond ? '' : ' :: ' + (extra || '')));
  }
  function $(id) { return document.getElementById(id); }
  function text(id) { var e = $(id); return e ? e.textContent : '(no ' + id + ')'; }
  function isOpen(id) { return $(id).classList.contains('open'); }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  window.addEventListener('error', function (e) {
    results.push('FAIL 例外 :: ' + e.message + ' @' + e.filename + ':' + e.lineno);
  });
  window.addEventListener('unhandledrejection', function (e) {
    results.push('FAIL 例外(Promise) :: ' + (e.reason && e.reason.message ? e.reason.message : e.reason));
  });

  // confirm / alert はヘッドレスでは出せないので差し替える
  var alerts = [];
  window.confirm = function () { return true; };
  window.alert = function (m) { alerts.push(m); };

  function run() {
    var code = null;

    return Promise.resolve()
      .then(function () {
        // ログイン状態が分かるまでは「読み込み中」だけが見えている
        check('ログイン状態が分かるまでは起動中画面が出る',
          $('bootScreen').hidden === false &&
          $('loginScreen').hidden === true && $('appLayout').hidden === true,
          'boot=' + $('bootScreen').hidden + ' login=' + $('loginScreen').hidden +
          ' app=' + $('appLayout').hidden);

        root.KKAuth._signIn();
        return wait(30);
      })
      .then(function () {
        check('ログイン後はアプリ画面に切り替わる',
          $('loginScreen').hidden === true && $('appLayout').hidden === false);
        check('ヘッダに表示名が出る', text('userName') === 'テスト太郎', text('userName'));
        check('グループが無いときのサイドバー表示',
          $('groupList').textContent.indexOf('グループがまだありません') >= 0);

        // ── グループ作成 ──
        root.openNewGroupModal();
        check('作成モーダルが開く', isOpen('newGroupModal'));
        $('newGroupName').value = 'テスト旅行';
        ['あ', 'い', 'う'].forEach(function (n) {
          $('newMemberInput').value = n;
          root.addNewMember();
        });
        check('メンバー 3 人が並ぶ',
          $('newMemberList').querySelectorAll('.member-row').length === 3);
        root.createGroup();
        return wait(60);
      })
      .then(function () {
        check('作成モーダルが閉じる', !isOpen('newGroupModal'));
        code = Object.keys(root.KKStore._data.groups)[0];
        check('サイドバーにグループ名が出る',
          $('groupList').textContent.indexOf('テスト旅行') >= 0, $('groupList').textContent);
        check('グループ画面が開く',
          $('main').textContent.indexOf('テスト旅行') >= 0);
        check('残高カードが 3 枚',
          $('main').querySelectorAll('.balance-card').length === 3);

        // ── 支払いを記録（あ が 3000 円、3 人で割る）──
        root.openPaymentModal();
        check('支払いモーダルが開く', isOpen('paymentModal'));
        check('支払った人の選択肢が 3 人', $('payPayer').options.length === 3);
        check('割り勘対象が既定で全員選択',
          $('payParticipants').querySelectorAll('.chip.selected').length === 3);
        $('payMemo').value = '宿代';
        $('payAmount').value = '3000';
        root.recordPayment();
        return wait(60);
      })
      .then(function () {
        check('支払いモーダルが閉じる', !isOpen('paymentModal'));
        var items = $('main').querySelectorAll('.payment-item');
        check('履歴に 1 件出る', items.length === 1, 'items=' + items.length);
        check('履歴にメモと金額が出る',
          $('main').textContent.indexOf('宿代') >= 0 && $('main').textContent.indexOf('3,000') >= 0);
        check('残高が +2,000 / -1,000 / -1,000',
          $('main').textContent.indexOf('+¥2,000') >= 0 &&
          ($('main').textContent.match(/−¥1,000/g) || []).length === 2,
          $('main').querySelector('.balance-grid').textContent);

        // ── 編集（3000 → 6000）──
        var pid = Object.keys(root.KKStore._data.groups[code].payments)[0];
        root.openEditPayModal(pid);
        check('編集モーダルのタイトルが「編集」',
          document.querySelector('#paymentModal .modal-title').textContent.indexOf('編集') >= 0);
        check('編集モーダルに既存の金額が入る', $('payAmount').value === '3000', $('payAmount').value);
        $('payAmount').value = '6000';
        root.recordPayment();
        return wait(60);
      })
      .then(function () {
        check('編集が履歴に反映される', $('main').textContent.indexOf('6,000') >= 0);
        check('編集で件数は増えない', $('main').querySelectorAll('.payment-item').length === 1);

        // ── 他端末からの追加がリアルタイムで入る ──
        var members = Object.keys(root.KKStore._data.groups[code].members);
        var parts = {}; members.forEach(function (m) { parts[m] = true; });
        return root.KKStore._remoteAddPayment(code, {
          date: '2026-09-20', memo: '別端末から', payerId: members[1], amount: 1200, participants: parts
        }).then(function () { return wait(60); });
      })
      .then(function () {
        check('他端末の追加が画面に入る',
          $('main').textContent.indexOf('別端末から') >= 0 &&
          $('main').querySelectorAll('.payment-item').length === 2);
        var remoteRow = Array.prototype.filter.call(
          $('main').querySelectorAll('.payment-item'),
          function (el) { return el.textContent.indexOf('別端末から') >= 0; })[0];
        check('他端末から入った行がハイライトされる',
          !!remoteRow && remoteRow.classList.contains('flash'),
          remoteRow ? remoteRow.className : '(行が無い)');

        // ── 清算 ──
        root.openSettlement();
        check('清算モーダルが開く', isOpen('settlementModal'));
        var st = $('settlementContent').textContent;
        check('送金リストが出る', $('settlementContent').querySelectorAll('.settlement-item').length > 0, st);
        root.closeModal('settlementModal');

        // ── 削除 ──
        var pid2 = Object.keys(root.KKStore._data.groups[code].payments)[0];
        root.deletePay(pid2);
        return wait(60);
      })
      .then(function () {
        check('削除すると履歴が 1 件になる',
          $('main').querySelectorAll('.payment-item').length === 1);

        // ── グループ設定 ──
        root.openSettings();
        check('設定モーダルが開く', isOpen('settingsModal'));
        check('共有コードが表示される', text('shareCodeBox') === code, text('shareCodeBox'));
        check('メンバーが入力欄で並ぶ',
          $('editMemberList').querySelectorAll('input').length === 3);
        $('editGroupName').value = 'テスト旅行2';
        root.setEditMemberName(0, 'あー');
        $('editMemberInput').value = 'え';
        root.addEditMember();
        root.saveSettings();
        return wait(80);
      })
      .then(function () {
        check('グループ名の変更が反映される',
          $('main').textContent.indexOf('テスト旅行2') >= 0);
        check('メンバー名の変更が反映される',
          $('main').querySelector('.balance-grid').textContent.indexOf('あー') >= 0);
        check('メンバー追加が反映される（残高カード 4 枚）',
          $('main').querySelectorAll('.balance-card').length === 4,
          'cards=' + $('main').querySelectorAll('.balance-card').length);

        // ── コードで参加（別の人が作ったグループ）──
        root.KKStore._seedGroup('ZZZ999', 'テスト他人のグループ', ['か', 'き']);
        root.openJoinModal();
        check('参加モーダルが開く', isOpen('joinGroupModal'));
        $('joinCodeInput').value = 'zzz999';   // 小文字で入れても大文字に直る
        root.doJoin();
        return wait(120);
      })
      .then(function () {
        check('参加モーダルが閉じる', !isOpen('joinGroupModal'));
        check('参加したグループがサイドバーに出る',
          $('groupList').textContent.indexOf('テスト他人のグループ') >= 0, $('groupList').textContent);
        check('参加したグループが開く',
          $('main').textContent.indexOf('テスト他人のグループ') >= 0);

        // 存在しないコード
        root.openJoinModal();
        $('joinCodeInput').value = 'NOPE00';
        root.doJoin();
        return wait(120);
      })
      .then(function () {
        check('存在しないコードはエラーを表示する',
          text('joinFeedback').indexOf('見つかりませんでした') >= 0, text('joinFeedback'));
        root.closeModal('joinGroupModal');

        // ── 退出 ──
        root.openSettings();
        root.leaveGroup();
        return wait(120);
      })
      .then(function () {
        check('退出すると一覧から消える',
          $('groupList').textContent.indexOf('テスト他人のグループ') < 0, $('groupList').textContent);
        check('退出してもグループのデータは残る',
          !!root.KKStore._data.groups['ZZZ999']);

        // ── ログアウト ──
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る',
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
          $('loginScreen').hidden === false && $('appLayout').hidden === true);
        check('想定外の alert が出ていない', alerts.length === 0, alerts.join(' / '));

        // ログインの失敗（iPhone Safari の auth/missing-initial-state など）は
        // このトーストでしか利用者に見えないので、表示経路が生きているかを見る
        root.KKUI.toast('ログインに失敗しました: Firebase: Unable to process request ' +
          'due to missing initial state. (auth/missing-initial-state).', 'error');
        var toasts = document.querySelectorAll('.toast-box .toast.toast-error');
        var last = toasts[toasts.length - 1];
        check('ログイン失敗の文言が赤いトーストで画面に出る',
          !!last && last.textContent.indexOf('missing initial state') >= 0,
          last ? last.textContent : '(トーストが出ていない)');
      })
      .catch(function (e) {
        results.push('FAIL 途中で落ちた :: ' + (e && e.message ? e.message : e) +
          ' @' + (e && e.stack ? String(e.stack).split('\n')[1] : ''));
      })
      .then(function () {
        var failed = results.filter(function (r) { return r.indexOf('FAIL') === 0; });
        beacon('=== UI SMOKE: ' + (results.length - failed.length) + ' 件通過 / ' +
          failed.length + ' 件失敗 ===');
        results.forEach(function (r) { beacon(r); });
        document.title = failed.length === 0 ? 'UI-SMOKE-PASS' : 'UI-SMOKE-FAIL';
        document.body.setAttribute('data-smoke', results.join(' | '));
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(run, 50); });
  else setTimeout(run, 50);
})(window);
