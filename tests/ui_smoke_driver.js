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
