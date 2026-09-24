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

        return wait(20);
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
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥2,400') >= 0,
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
          $('main').querySelector('.balance-grid').textContent.indexOf('+¥3,000') >= 0,
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

      // ══ 工事4a: CSV 出力 ══
      .then(function () {
        root.openExportModal();
        check('CSV 出力モーダルが開く', isOpen('exportModal'));
        check('CSV のボタンが 2 つ出る',
          $('exportBtns').querySelectorAll('.export-btn-row').length === 2);
        check('残高 CSV は今の表示モードで出す旨が出る',
          $('exportBtns').textContent.indexOf('未清算のみ') >= 0,
          $('exportBtns').textContent);
        root.closeModal('exportModal');

        var p = root.buildPaymentsCsv();
        check('支払い CSV の先頭が BOM', p.text.charCodeAt(0) === 0xFEFF);
        var rows = p.text.slice(1).replace(/\r\n$/, '').split('\r\n');
        check('支払い CSV のヘッダが仕様どおり',
          rows[0] === '日付,メモ,支払った人,金額,割り勘対象,1人あたり,清算状態', rows[0]);
        check('支払い CSV の 1 行目が画面の先頭と同じ支払い',
          rows[1].indexOf('テスト2回目の支払い') >= 0 && rows[1].indexOf('1200') >= 0, rows[1]);
        check('支払い CSV に清算状態が入る',
          rows[1].split(',').pop().indexOf('清算済み') === 0, rows[1]);
        check('支払い CSV のファイル名にグループ名と日付が入る',
          p.name.indexOf('テスト清算_支払い_') === 0 && /\d{8}\.csv$/.test(p.name), p.name);

        var b = root.buildBalancesCsv();
        var brows = b.text.slice(1).replace(/\r\n$/, '').split('\r\n');
        check('残高 CSV の 1 行目が未清算のみのコメント行',
          brows[0] === '# 残高（未清算のみ）', brows[0]);
        check('残高 CSV のヘッダが仕様どおり',
          brows[1] === 'メンバー,払った合計,負担分,残高', brows[1]);
        check('残高 CSV のファイル名が残高になっている',
          b.name.indexOf('テスト清算_残高_') === 0, b.name);

        root.setBalanceMode('all');
        return wait(40);
      })
      .then(function () {
        var b2 = root.buildBalancesCsv();
        check('累計に切り替えると残高 CSV のコメント行も累計になる',
          b2.text.slice(1).split('\r\n')[0] === '# 残高（累計）',
          b2.text.slice(1).split('\r\n')[0]);
        root.openExportModal();
        check('CSV モーダルの注記も累計になる',
          $('exportBtns').textContent.indexOf('累計') >= 0);
        root.closeModal('exportModal');
        root.setBalanceMode('unsettled');
        return wait(40);
      })

      // ══ 工事4a: アプリ内ブラウザの案内 ══
      .then(function () {
        check('通常のブラウザでは案内が出ていない', $('inAppNotice').hidden === true);
        check('判定の関数が UA を見ている（LINE の UA なら true）',
          root.Env.isInAppBrowser('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Line/14.5.0') === true);
        check('普通の Safari なら false',
          root.Env.isInAppBrowser('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1') === false);

        // UA を差し替えて、起動時の判定が案内を出すことを確かめる
        var realUA = navigator.userAgent;
        try {
          Object.defineProperty(navigator, 'userAgent', {
            value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Line/14.5.0',
            configurable: true
          });
          root.checkInAppBrowser();
          check('アプリ内ブラウザの UA なら案内が出る', $('inAppNotice').hidden === false);
          check('案内に Safari / Chrome で開く説明が出る',
            $('inAppNotice').textContent.indexOf('Safari で開く') >= 0);
          check('URL をコピーするボタンがある', !!$('btnCopyUrl'));
          check('案内が出てもログインボタンは残る（誤判定に備える）',
            !!$('btnLogin') && $('btnLogin').hidden === false &&
            $('btnLogin').disabled === false &&
            $('btnLogin').textContent.indexOf('Google') >= 0,
            $('btnLogin') ? $('btnLogin').textContent : '(ボタンが無い)');
          Object.defineProperty(navigator, 'userAgent', { value: realUA, configurable: true });
          root.checkInAppBrowser();
          check('通常の UA に戻すと案内が消える', $('inAppNotice').hidden === true);
        } catch (e) {
          check('UA を差し替えて案内の出し分けを確かめる', false, e.message);
        }
        return wait(20);
      })

      // ══ 工事4b-B: 誰が入力したか・誰がチェックしたか ══
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
          /\d{2}\/\d{2} \d{2}:\d{2}/.test(by.textContent),
          by ? by.textContent : '(表示が無い)');
        root.closeModal('settlementModal');
        return wait(40);
      })

      // ══ 工事4b-C: 過去の清算の件数制限 ══
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

      // ══ 工事4c: スマホ幅で入力欄が 16px（iOS の自動ズーム対策）══
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
