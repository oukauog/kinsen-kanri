/*
 * ui.js — v2 の画面。index.html の onclick から呼ばれる関数はすべてここで global に生やす
 *
 * 構成:
 *   状態 → 描画（サイドバー / メイン）→ 各操作（モーダル）→ 起動
 *
 * 表示の作り方は v1 を踏襲（innerHTML を組み立てて差し込む）。
 * 差分は「データが Firebase のリスナー経由で入ってくる」ことだけで、
 * 描画そのものは v1 と同じ見た目になるようにしてある。
 */
(function (root) {
  'use strict';

  var Calc = root.Calc;
  var Store = root.KKStore;
  var Auth = root.KKAuth;
  var Migrate = root.Migrate;
  var Settle = root.Settle;
  var Csv = root.Csv;
  var Env = root.Env;
  var GroupOrder = root.KKGroupOrder;

  var LS_LAST_GROUP = 'kk_v2_lastGroup';   // v2 が使う localStorage は kk_v2_* のみ
  var LS_BALANCE_MODE = 'kk_v2_balanceMode';

  // 残高カードの表示: 'unsettled'（未清算のみ。既定） / 'all'（累計）
  var balanceMode = (function () {
    try {
      return localStorage.getItem(LS_BALANCE_MODE) === 'all' ? 'all' : 'unsettled';
    } catch (e) { return 'unsettled'; }
  })();

  // ---- 状態 -----------------------------------------------------------

  var me = null;              // Firebase の user
  var myGroups = {};          // { code: { joinedAt, order? } }
  var groupOrderAttached = false;   // サイドバーの並べ替えを付けたか（1 回だけ）
  var metas = {};             // { code: meta | null }   ← null は「消えたグループ」
  var metaOff = {};           // { code: 監視を外す関数 }
  var currentCode = null;     // 開いているグループの共有コード
  var currentGroup = null;    // { meta, members, payments }
  var seenPaymentAt = null;   // ハイライト用 { pid: 最初に見えた時刻 }。null は「初回描画前」
  var FLASH_MS = 1600;        // 新しく入った行を光らせる時間（css の kk-flash と合わせる）
  var showAllSettlements = false;   // 過去の清算を全件出すか（保存しない。工事4b）
  var PAST_LIMIT = 5;              // 折りたたみ時に出す件数
  var newMembers = [];        // 新規グループ作成モーダルの作業用
  var editMembers = [];       // グループ設定モーダルの作業用
  var editingPaymentId = null;

  // ---- 小道具 ---------------------------------------------------------

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function money(n) { return Calc.money(n); }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function openModal(id) { $(id).classList.add('open'); }
  function closeModal(id) { $(id).classList.remove('open'); }

  /** 画面下に短いメッセージを出す。kind は '' / 'error' */
  function toast(msg, kind) {
    var box = $('toastBox');
    if (!box) {
      box = document.createElement('div');
      box.id = 'toastBox';
      box.className = 'toast-box';
      document.body.appendChild(box);
    }
    var el = document.createElement('div');
    el.className = 'toast' + (kind === 'error' ? ' toast-error' : '');
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(function () { el.classList.add('out'); }, kind === 'error' ? 5000 : 2600);
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); },
      kind === 'error' ? 5400 : 3000);
  }

  /** エラーを利用者向けの 1 行にする */
  function errText(err) {
    if (err && (err.code === 'PERMISSION_DENIED' || err.code === 'permission-denied')) {
      return 'アクセスが拒否されました（権限がありません）';
    }
    return err && err.message ? err.message : String(err);
  }

  /**
   * Firebase の失敗を握りつぶさない（v1 の反省点。仕様書 §0-3、§5.7）。
   * store.js の wrapWrite が既にトーストを出したものは、印（__kkReported）で
   * 二重表示を避ける。
   */
  function fail(prefix) {
    return function (err) {
      console.error(prefix, err);
      if (err && err.__kkReported) return;
      toast(prefix + ': ' + errText(err), 'error');
    };
  }

  /** members / payments のオブジェクトを表示用の配列にする */
  function memberList(group) {
    return Calc.normalizeMembers(group && group.members ? group.members : {});
  }
  function paymentList(group) {
    var ps = Calc.normalizePayments(group && group.payments ? group.payments : {});
    return ps.sort(function (a, b) {
      return String(b.date || '').localeCompare(String(a.date || '')) ||
        ((b.createdAt || 0) - (a.createdAt || 0));
    });
  }
  function memberName(members, mid) {
    for (var i = 0; i < members.length; i++) if (members[i].id === mid) return members[i].name;
    return '?';
  }

  /** ミリ秒 → 「2026/09/24 18:30」 */
  function dateTime(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '/' + p(d.getMonth() + 1) + '/' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** ミリ秒 → 「09/24 18:30」（送金チェックの横に出す短い形） */
  function shortDateTime(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return p(d.getMonth() + 1) + '/' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** 開いているグループの清算レコード（無ければ {}） */
  function settlementsOf(group) {
    return (group && group.settlements) ? group.settlements : {};
  }

  // ---- ログイン画面の出し分け ------------------------------------------

  function hideBoot() {
    var b = $('bootScreen');
    if (b) b.hidden = true;
  }

  function showLoggedOut() {
    hideBoot();
    $('loginScreen').hidden = false;
    $('appLayout').hidden = true;
    $('userBar').hidden = true;
    closeSidebar();
  }

  function showLoggedIn(user) {
    hideBoot();
    $('loginScreen').hidden = true;
    $('appLayout').hidden = false;
    $('userBar').hidden = false;
    $('userName').textContent = user.displayName || user.email || '';
    var img = $('userAvatar');
    if (user.photoURL) { img.src = user.photoURL; img.hidden = false; }
    else { img.hidden = true; }
  }

  function doLogin() {
    var btn = $('btnLogin');
    if (btn) { btn.disabled = true; btn.textContent = 'ログイン中…'; }
    Auth.login().catch(function (err) {
      fail('ログインに失敗しました')(err);
    }).then(function () {
      if (btn) { btn.disabled = false; btn.textContent = 'Google でログイン'; }
    });
  }

  function doLogout() {
    Store.stopWatchMyGroups();
    Store.stopWatchGroup();
    Object.keys(metaOff).forEach(function (c) { metaOff[c](); });
    metaOff = {}; metas = {}; myGroups = {};
    currentCode = null; currentGroup = null; seenPaymentAt = null;
    Auth.logout().catch(fail('ログアウトに失敗しました'));
  }

  // ---- サイドバー -----------------------------------------------------

  /** 表示順（order → 無ければ joinedAt、同点はコード順。js/group_order.js）*/
  function sortedCodes() {
    return GroupOrder.sortCodes(myGroups);
  }

  function renderSidebar() {
    var el = $('groupList');
    var codes = sortedCodes();
    if (codes.length === 0) {
      el.innerHTML = '<div class="sidebar-empty">グループがまだありません</div>';
      return;
    }
    el.innerHTML = codes.map(function (code) {
      var meta = metas[code];
      if (meta === null) {
        // グループ本体が消えている（他の人が削除した、またはコードが間違っていた）
        // つまみは付けない（自分では動かせない）が、並びの中には残す
        return '<div class="group-item missing" data-code="' + code + '">' +
          '<span class="group-item-name">（削除されたグループ）</span>' +
          '<button class="group-item-x" title="一覧から消す" ' +
          'onclick="dismissMissingGroup(\'' + code + '\')">&#x2715;</button></div>';
      }
      var name = meta && meta.name ? meta.name : '読み込み中…';
      // 右端のつまみ（⋮⋮）でだけ並べ替える。つまみを押しても selectGroup は起こさない
      return '<div class="group-item' + (code === currentCode ? ' active' : '') + '" ' +
        'data-code="' + code + '" onclick="selectGroup(\'' + code + '\')">' +
        '<span class="group-item-name">' + esc(name) + '</span>' +
        '<span class="group-item-handle" title="ドラッグで並べ替え" ' +
        'onclick="event.stopPropagation()">&#x22EE;&#x22EE;</span></div>';
    }).join('');
  }

  /** つまみのドラッグ＆ドロップで並びが確定したら、その順で order = 0..n-1 を書く */
  function saveGroupOrder(codes) {
    // 描画とドロップの間に一覧から消えたコードに order だけ書かないよう、今の一覧にあるものに絞る
    var list = codes.filter(function (c) { return !!myGroups[c]; });
    Store.setGroupOrder(list).catch(fail('グループの並び順を保存できませんでした'));
  }

  // ---- メイン画面 -----------------------------------------------------

  function renderMain() {
    var main = $('main');
    if (!currentCode) {
      main.innerHTML = '<div class="empty-state"><div class="icon">&#x1F465;</div>' +
        '<h2>グループを選択してください</h2>' +
        '<p>左サイドバーからグループを選ぶか、<br>新しいグループを作成してください</p></div>';
      return;
    }
    if (!currentGroup) {
      main.innerHTML = '<div class="empty-state"><div class="icon">&#x23F3;</div>' +
        '<h2>読み込み中…</h2></div>';
      return;
    }

    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    // 残高は既定で「未清算のみ」。確認中（pending）はどちらのモードでも外す（§5.3.1、§5.4）
    var pendings = Settle.pickPending(pays);
    var balSource = balanceMode === 'all'
      ? Settle.pickAllButPending(pays)
      : Settle.pickUnsettled(pays);
    var bal = Calc.calcBalances(members, balSource);
    var groupName = currentGroup.meta && currentGroup.meta.name ? currentGroup.meta.name : '(名称未設定)';

    var sorted = members.slice().sort(function (a, b) {
      return (bal[a.id] || 0) - (bal[b.id] || 0);
    });
    var nextMember = sorted.filter(function (m) { return (bal[m.id] || 0) < -0.5; })[0];
    var nextId = nextMember ? nextMember.id : null;

    var balHTML = sorted.map(function (m) {
      var b = bal[m.id] || 0;
      var cls = b > 0.5 ? 'positive' : b < -0.5 ? 'negative' : '';
      var label = b > 0.5 ? '多く払っている' : b < -0.5 ? '借りがある' : 'ほぼ均等';
      var sign = b >= 0 ? '+' : '−';
      return '<div class="balance-card ' + cls + '">' +
        (m.id === nextId ? '<div class="next-badge">次は払う番？</div>' : '') +
        '<div class="balance-name">' + esc(m.name) + '</div>' +
        '<div class="balance-amount">' + sign + money(b) + '</div>' +
        '<div class="balance-label">' + label + '</div></div>';
    }).join('');

    // 他の端末で追加された行を一瞬光らせる（初回描画では光らせない）。
    // 「初めて見えた時刻」で判定する。描画が続けて走っても消えないようにするため。
    var now = Date.now();
    var firstRender = (seenPaymentAt === null);
    if (firstRender) seenPaymentAt = {};
    var fresh = {};
    var alive = {};
    pays.forEach(function (p) {
      alive[p.id] = true;
      if (!(p.id in seenPaymentAt)) seenPaymentAt[p.id] = firstRender ? 0 : now;
      if (now - seenPaymentAt[p.id] < FLASH_MS) fresh[p.id] = true;
    });
    Object.keys(seenPaymentAt).forEach(function (id) {
      if (!alive[id]) delete seenPaymentAt[id];
    });

    var paysHTML = pays.length === 0
      ? '<div class="no-payments">まだ記録がありません。</div>'
      : '<div class="payment-list">' + pays.map(function (p) {
        var per = p.participants.length > 0 ? p.amount / p.participants.length : 0;
        var partNames = p.participants.map(function (mid) {
          return memberName(members, mid);
        }).join('・');
        var isPending = p.pending === true;
        var isSettled = p.settlementId != null;
        var cls = 'payment-item' + (fresh[p.id] ? ' flash' : '') +
          (isPending ? ' pending' : '') + (isSettled ? ' settled' : '');
        var badge = isSettled ? '<span class="pay-badge settled">清算済み</span>'
          : isPending ? '<span class="pay-badge pending">確認中</span>' : '';
        var amountHTML = isPending
          ? '<div class="payment-total">確認中</div>'
          : '<div class="payment-total">' + money(p.amount) + '</div>' +
            '<div class="payment-per">1人 ' + money(per) + '</div>';
        // 清算済みは編集・削除できない（データ層でも止めている）
        var editBtn = isSettled
          ? '<button class="btn-edit" onclick="lockedNotice()" title="清算済み">&#x270F;</button>'
          : '<button class="btn-edit" onclick="openEditPayModal(\'' + p.id + '\')" title="編集">&#x270F;</button>';
        var delBtn = isSettled
          ? '<button class="btn-delete" onclick="lockedNotice()" title="清算済み">&#x2715;</button>'
          : '<button class="btn-delete" onclick="deletePay(\'' + p.id + '\')" title="削除">&#x2715;</button>';
        return '<div class="' + cls + '">' +
          '<div class="payment-date">' + esc(p.date) + '</div>' +
          '<div class="payment-info">' +
            '<div class="payment-payer">' + esc(p.memo || '支払い') + badge + '</div>' +
            '<div class="payment-memo">' + esc(memberName(members, p.payerId)) + ' が支払い</div>' +
            '<div class="payment-participants">' + esc(partNames) + '</div>' +
            // 入力者は、名前が保存されている支払いだけ（移行分・工事4b 以前には無い）
            (p.createdByName
              ? '<div class="payment-by">入力: ' + esc(p.createdByName) + '</div>' : '') +
          '</div>' +
          '<div class="payment-amounts">' + amountHTML + '</div>' +
          editBtn + delBtn +
          '</div>';
      }).join('') + '</div>';

    main.innerHTML =
      '<div class="group-header">' +
        '<div class="group-title">' + esc(groupName) + '</div>' +
        '<div class="group-actions">' +
          '<button class="btn btn-primary" onclick="openPaymentModal()">&#xFF0B; 支払いを記録</button>' +
          '<button class="btn btn-secondary" onclick="openSettlement()">清算</button>' +
          '<button class="btn btn-secondary" onclick="openExportModal()">CSV出力</button>' +
          '<button class="btn btn-secondary" onclick="openSettings()">設定</button>' +
        '</div></div>' +
      '<div class="section-head">' +
        '<div class="section-title">残高 — ' +
        (balanceMode === 'all' ? '累計' : '未清算分') + '</div>' +
        (pendings.length
          ? '<span class="pending-note">金額確認中 ' + pendings.length +
            ' 件（計算に含まれていません）</span>' : '') +
        '<div class="balance-mode">' +
          '<button class="' + (balanceMode === 'unsettled' ? 'active' : '') +
          '" onclick="setBalanceMode(\'unsettled\')">未清算のみ</button>' +
          '<button class="' + (balanceMode === 'all' ? 'active' : '') +
          '" onclick="setBalanceMode(\'all\')">累計を見る</button>' +
        '</div>' +
      '</div>' +
      '<div class="balance-grid">' + balHTML + '</div>' +
      '<div class="section-title">支払い履歴</div>' + paysHTML;
  }

  function render() {
    renderSidebar();
    renderMain();
    // 清算モーダルを開いたまま他端末の変更が届いたら、その場で描き直す
    var sm = $('settlementModal');
    if (sm && sm.classList.contains('open') && currentGroup) renderSettlement();
  }

  function setBalanceMode(mode) {
    balanceMode = (mode === 'all') ? 'all' : 'unsettled';
    try { localStorage.setItem(LS_BALANCE_MODE, balanceMode); } catch (e) { /* noop */ }
    renderMain();
  }

  function lockedNotice() {
    toast('清算済みの支払いは編集できません。先に清算を取り消してください', 'error');
  }

  // ---- グループの選択・監視 -------------------------------------------

  function selectGroup(code) {
    if (currentCode === code) { closeSidebar(); return; }
    currentCode = code;
    currentGroup = null;
    seenPaymentAt = null;
    showAllSettlements = false;   // グループを変えたら過去の清算は 5 件に戻す
    try { localStorage.setItem(LS_LAST_GROUP, code); } catch (e) { /* 使えなくても動く */ }
    closeSidebar();
    render();
    Store.watchGroup(code, function (g) {
      if (currentCode !== code) return;
      if (g === null) {
        // 他の人が削除した／権限が無くなった
        currentGroup = null;
        currentCode = null;
        seenPaymentAt = null;
        try { localStorage.removeItem(LS_LAST_GROUP); } catch (e) { /* noop */ }
        toast('このグループは削除されました');
        render();
        return;
      }
      currentGroup = g;
      render();
    }, function (err) {
      currentGroup = null;
      render();
      fail('グループを読み込めませんでした')(err);
    });
  }

  function dismissMissingGroup(code) {
    if (!confirm('このグループを一覧から消しますか？')) return;
    Store.leaveGroup(code).catch(fail('一覧から消せませんでした'));
  }

  /** 参加グループの meta 監視を、一覧の増減に合わせて張り直す */
  function syncMetaWatchers() {
    var codes = Object.keys(myGroups);
    codes.forEach(function (code) {
      if (metaOff[code]) return;
      if (!(code in metas)) metas[code] = undefined;   // 読み込み中
      metaOff[code] = Store.watchMeta(code, function (meta) {
        metas[code] = meta === null ? null : meta;
        renderSidebar();
        if (code === currentCode) renderMain();
      }, function (err) {
        console.error('meta', code, err);
        metas[code] = null;
        renderSidebar();
      });
    });
    Object.keys(metaOff).forEach(function (code) {
      if (codes.indexOf(code) >= 0) return;
      metaOff[code](); delete metaOff[code]; delete metas[code];
    });
  }

  // ---- サイドバー開閉（v1 と同じ） -------------------------------------

  function toggleSidebar() {
    var s = document.querySelector('.sidebar');
    var b = document.querySelector('.sidebar-backdrop');
    var opening = !s.classList.contains('open');
    s.classList.toggle('open', opening);
    b.classList.toggle('open', opening);
  }
  function closeSidebar() {
    var s = document.querySelector('.sidebar');
    var b = document.querySelector('.sidebar-backdrop');
    if (s) s.classList.remove('open');
    if (b) b.classList.remove('open');
  }

  // ---- グループ作成 ---------------------------------------------------

  function openNewGroupModal() {
    newMembers = [];
    $('newGroupName').value = '';
    $('newMemberInput').value = '';
    renderNewMemberList();
    openModal('newGroupModal');
    setTimeout(function () { $('newGroupName').focus(); }, 50);
  }
  function renderNewMemberList() {
    $('newMemberList').innerHTML = newMembers.map(function (n, i) {
      return '<div class="member-row"><span class="member-row-name">' + esc(n) + '</span>' +
        '<button class="member-row-del" onclick="removeNewMember(' + i + ')">&#x2715;</button></div>';
    }).join('');
  }
  function removeNewMember(i) { newMembers.splice(i, 1); renderNewMemberList(); }
  function addNewMember() {
    var el = $('newMemberInput');
    var name = el.value.trim();
    if (!name) return;
    newMembers.push(name); el.value = '';
    renderNewMemberList(); el.focus();
  }
  function createGroup() {
    var name = $('newGroupName').value.trim();
    if (!name) { alert('グループ名を入力してください'); return; }
    if (newMembers.length < 2) { alert('メンバーを2人以上追加してください'); return; }
    Store.createGroup(name, newMembers, GroupOrder.nextOrder(myGroups)).then(function (code) {
      closeModal('newGroupModal');
      toast('グループを作成しました（共有コード ' + code + '）');
      selectGroup(code);
    }).catch(fail('グループを作成できませんでした'));
  }

  // ---- コードで参加 ---------------------------------------------------

  function openJoinModal() {
    $('joinCodeInput').value = '';
    $('joinFeedback').textContent = '';
    openModal('joinGroupModal');
    setTimeout(function () { $('joinCodeInput').focus(); }, 50);
  }
  function doJoin() {
    var code = ($('joinCodeInput').value || '').trim().toUpperCase();
    var fb = $('joinFeedback');
    if (code.length < 4) { fb.textContent = 'コードを入力してください'; return; }
    if (myGroups[code]) {
      fb.textContent = 'このグループにはすでに参加しています';
      return;
    }
    fb.textContent = '確認中…';
    Store.readMeta(code).then(function (meta) {
      // ① v2 のグループがある → 従来どおりの参加
      if (meta) {
        if (!confirm('「' + (meta.name || '(名称未設定)') + '」に参加しますか？')) {
          fb.textContent = '';
          return;
        }
        return Store.joinGroup(code, GroupOrder.nextOrder(myGroups)).then(function () {
          closeModal('joinGroupModal');
          toast('「' + (meta.name || '') + '」に参加しました');
          selectGroup(code);
        });
      }
      // ② 無ければ旧バージョンのルームを 1 回だけ読む（読み取りのみ）
      return Store.readRoom(code).then(function (room) {
        if (!room) { fb.textContent = 'そのコードのグループは見つかりませんでした'; return; }
        startMigration(code, room);
      });
    }).catch(function (err) {
      fb.textContent = '';
      fail('参加できませんでした')(err);
    });
  }

  // ---- 旧バージョンからの取り込み（工事2）------------------------------

  var migrateCtx = null;    // { code, room, summary }

  function skipText(sk) {
    var parts = [];
    if (sk.deletedGroups) parts.push('削除済みのグループ ' + sk.deletedGroups + ' 件');
    if (sk.deletedPayments) parts.push('削除済みの支払い ' + sk.deletedPayments + ' 件');
    if (sk.orphanPayments) parts.push('グループが分からない支払い ' + sk.orphanPayments + ' 件');
    return parts.length ? parts.join('、') + ' は取り込みません。' : '';
  }

  /** 旧ルームが見つかったときの入口。1 件なら確認だけ、2 件以上なら選択ダイアログ */
  function startMigration(code, room) {
    var summary = Migrate.summarizeRoom(room);
    if (summary.groups.length === 0) {
      $('joinFeedback').textContent = 'そのコードには取り込めるグループがありませんでした';
      return;
    }
    migrateCtx = { code: code, room: room, summary: summary };

    if (summary.groups.length === 1) {
      var g = summary.groups[0];
      var msg = '旧バージョンのデータが見つかりました。\n「' + g.name +
        '」（支払い ' + g.paymentCount + ' 件）を取り込んで参加しますか？';
      var sk = skipText(summary.skipped);
      if (sk) msg += '\n\n※ ' + sk;
      if (!confirm(msg)) {
        migrateCtx = null;
        $('joinFeedback').textContent = '';
        return;
      }
      runMigration(g.id);
      return;
    }

    $('migrateContent').innerHTML =
      '<p class="migrate-note">このコードには複数のグループがあります。' +
      'コード <strong>' + esc(code) + '</strong> を引き継ぐグループを 1 つ選んでください' +
      '（他のグループには新しいコードを発行します）。</p>' +
      '<div class="migrate-pick-list">' +
      summary.groups.map(function (g, i) {
        return '<label class="migrate-pick">' +
          '<input type="radio" name="migratePick" value="' + esc(g.id) + '"' +
          (i === 0 ? ' checked' : '') + '>' +
          '<span><span class="migrate-pick-name">' + esc(g.name) + '</span>' +
          '<span class="migrate-pick-sub">メンバー ' + g.memberCount + ' 人 ・ 支払い ' +
          g.paymentCount + ' 件</span></span></label>';
      }).join('') + '</div>' +
      (skipText(summary.skipped) ? '<div class="migrate-skip">※ ' +
        esc(skipText(summary.skipped)) + '</div>' : '');

    setMigrateBusy(false);
    closeModal('joinGroupModal');
    openModal('migrateModal');
  }

  function setMigrateBusy(busy) {
    var btn = $('migrateConfirmBtn');
    if (!btn) return;
    btn.disabled = !!busy;
    btn.textContent = busy ? '取り込み中…' : '取り込む';
  }

  function cancelMigrate() {
    migrateCtx = null;
    closeModal('migrateModal');
  }

  function confirmMigrate() {
    var el = document.querySelector('#migrateContent input[name="migratePick"]:checked');
    if (!el) { alert('グループを 1 つ選んでください'); return; }
    runMigration(el.value);
  }

  /** 新しいコードを必要数だけ発行して変換し、書き込む */
  function runMigration(pickGroupId) {
    if (!migrateCtx) return;
    var ctx = migrateCtx;
    var need = Math.max(0, ctx.summary.groups.length - 1);
    var me = Auth.user();
    setMigrateBusy(true);
    $('joinFeedback').textContent = '取り込み中…';

    Store.allocCodes(need).then(function (newCodes) {
      var conv = Migrate.convertRoom(ctx.room, {
        code: ctx.code,
        uid: me ? me.uid : '',
        pickGroupId: pickGroupId,
        newCodes: newCodes,
        now: Date.now()
      });
      return Store.migrateRoom(conv).then(function (res) {
        showMigrateResult(ctx, conv, res);
      });
    }).catch(function (err) {
      setMigrateBusy(false);
      $('joinFeedback').textContent = '';
      fail('取り込みに失敗しました')(err);
    });
  }

  function showMigrateResult(ctx, conv, res) {
    var already = res && res.already ? res.already : [];
    $('migrateResultContent').innerHTML =
      '<p class="migrate-note">旧バージョンのデータを取り込みました。' +
      '新しいコードは、いっしょに使う人に渡してください。</p>' +
      '<div class="migrate-result-list">' +
      conv.order.map(function (code) {
        var g = conv.groups[code];
        var tag = already.indexOf(code) >= 0
          ? '<span class="migrate-result-tag">（すでに取り込み済みでした。参加のみ）</span>' : '';
        return '<div class="migrate-result-item">' +
          '<div class="migrate-result-name">' + esc(g.meta.name) + tag + '</div>' +
          '<span class="migrate-result-code" onclick="copyCode(\'' + code + '\')" ' +
          'title="タップでコピー">' + code + '</span>' +
          '<div class="migrate-pick-sub">メンバー ' + Object.keys(g.members || {}).length +
          ' 人 ・ 支払い ' + Object.keys(g.payments || {}).length + ' 件</div>' +
          '</div>';
      }).join('') + '</div>' +
      (skipText(ctx.summary.skipped) ? '<div class="migrate-skip">※ ' +
        esc(skipText(ctx.summary.skipped)) + '</div>' : '');

    setMigrateBusy(false);
    $('joinFeedback').textContent = '';
    closeModal('migrateModal');
    closeModal('joinGroupModal');
    openModal('migrateResultModal');
  }

  function closeMigrateResult() {
    closeModal('migrateResultModal');
    var code = migrateCtx ? migrateCtx.code : null;
    migrateCtx = null;
    if (code) selectGroup(code);
  }

  /** 共有コードをクリップボードへ */
  function copyCode(code) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(function () {
        toast('コードをコピーしました: ' + code);
      }, function () {
        toast('コピーできませんでした（手で選択してください）', 'error');
      });
    } else {
      toast('この端末では自動コピーができません。コードを手で選択してください', 'error');
    }
  }

  // ---- 支払い ---------------------------------------------------------

  function openPaymentModal(payId) {
    if (!currentGroup) return;
    var members = memberList(currentGroup);
    if (members.length === 0) { alert('先にメンバーを追加してください'); return; }
    editingPaymentId = payId || null;
    var pay = null;
    if (payId) {
      pay = paymentList(currentGroup).filter(function (p) { return p.id === payId; })[0] || null;
    }
    if (pay && pay.settlementId != null) { lockedNotice(); return; }
    $('payDate').value = pay ? pay.date : today();
    $('payMemo').value = pay ? (pay.memo || '') : '';
    $('payPending').checked = !!(pay && pay.pending === true);
    $('payAmount').value = (pay && pay.pending !== true) ? pay.amount : '';
    onPendingToggle();
    $('payPayer').innerHTML = members.map(function (m) {
      return '<option value="' + m.id + '"' + (pay && pay.payerId === m.id ? ' selected' : '') +
        '>' + esc(m.name) + '</option>';
    }).join('');
    $('payParticipants').innerHTML = members.map(function (m) {
      var sel = !pay || pay.participants.indexOf(m.id) >= 0;
      return '<div class="chip' + (sel ? ' selected' : '') + '" data-id="' + m.id +
        '" onclick="toggleChip(this)">' + esc(m.name) + '</div>';
    }).join('');
    document.querySelector('#paymentModal .modal-title').textContent =
      pay ? '✏️ 支払いを編集' : '💳 支払いを記録';
    openModal('paymentModal');
  }
  function openEditPayModal(id) { openPaymentModal(id); }
  function toggleChip(el) { el.classList.toggle('selected'); }

  /** 「金額確認中」の切替。☑ のときは金額が空でも登録できる（§5.3.1）*/
  function onPendingToggle() {
    var pending = $('payPending').checked;
    var amount = $('payAmount');
    amount.placeholder = pending ? 'あとで入力' : '0';
    $('payPendingHint').textContent = pending
      ? '金額が決まったら、この支払いを編集してチェックを外してください'
      : '確認中の支払いは残高と清算の計算に入りません';
  }

  function recordPayment() {
    if (!currentCode) return;
    var date = $('payDate').value;
    var memo = $('payMemo').value.trim();
    var payerId = $('payPayer').value;
    var pending = $('payPending').checked;
    var amount = parseFloat($('payAmount').value);
    if (!date) { alert('日付を入力してください'); return; }
    if (pending) {
      amount = 0;                      // 金額確認中は 0 で持つ（計算からは外れる）
    } else if (!amount || amount <= 0) {
      alert('金額を入力してください'); return;
    }
    var chips = Array.prototype.slice.call(
      document.querySelectorAll('#payParticipants .chip.selected'));
    var ids = chips.map(function (el) { return el.dataset.id; });
    if (ids.length === 0) { alert('参加者を選択してください'); return; }
    // v1 と同じく、支払った人は必ず割り勘対象に含める
    if (ids.indexOf(payerId) < 0) ids.push(payerId);
    var participants = {};
    ids.forEach(function (id) { participants[id] = true; });

    var payload = {
      date: date, memo: memo, payerId: payerId, amount: amount,
      participants: participants, pending: pending
    };
    var p = editingPaymentId
      ? Store.updatePayment(currentCode, editingPaymentId, payload)
      : Store.addPayment(currentCode, payload);
    var wasEdit = !!editingPaymentId;
    editingPaymentId = null;
    closeModal('paymentModal');
    p.catch(fail(wasEdit ? '支払いを更新できませんでした' : '支払いを記録できませんでした'));
  }

  function deletePay(id) {
    if (!currentCode) return;
    if (!confirm('この記録を削除しますか？')) return;
    Store.removePayment(currentCode, id).catch(fail('削除できませんでした'));
  }

  // ---- 清算（工事3: 記録・チェック・取り消し）--------------------------

  function openSettlement() {
    if (!currentGroup) return;
    showAllSettlements = false;   // 開くたびに 5 件から（工事4b）
    renderSettlement();
    openModal('settlementModal');
  }

  /** 清算モーダルの中身を作る（開いている間、データが変わるたびに呼ばれる）*/
  function renderSettlement() {
    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    var pendings = Settle.pickPending(pays);
    var targets = Settle.pickUnsettled(pays);
    var me = Auth.user();
    var draft = Settle.buildSettlement(members, pays, {
      uid: me ? me.uid : '', now: Date.now()
    });

    // ── 今回の清算 ──
    var html = '<div class="settle-section"><div class="settle-head">今回の清算</div>';

    if (pendings.length) {
      html += '<div class="settle-warn">金額確認中の支払いが ' + pendings.length +
        ' 件あります。金額を確定してから清算してください。<ul>' +
        pendings.map(function (p) {
          return '<li>' + esc(p.date) + ' ' + esc(p.memo || '(メモなし)') + '</li>';
        }).join('') + '</ul></div>';
    }

    if (!draft) {
      html += '<div class="settlement-empty">' +
        (targets.length === 0 ? '未清算の支払いはありません。' : '🎉 未清算の貸し借りはありません！') +
        '</div>';
    } else {
      html += '<div class="settlement-list">' +
        Settle.transferList(draft).map(function (t) {
          return '<div class="settlement-item">' +
            '<span class="settlement-from">' + esc(t.fromName) + '</span>' +
            '<span class="settlement-arrow">&#x2192;</span>' +
            '<span class="settlement-to">' + esc(t.toName) + '</span>' +
            '<span class="settlement-amount">' + money(t.amount) + '</span></div>';
        }).join('') + '</div>' +
        '<div class="settle-sub">対象の支払い ' + targets.length + ' 件 ・ 送金 ' +
        Settle.transferList(draft).length + ' 本</div>' +
        '<div class="settle-confirm-row">' +
        '<button class="btn btn-primary" id="settleConfirmBtn" onclick="doConfirmSettlement()"' +
        (pendings.length ? ' disabled title="金額確認中の支払いがあります"' : '') +
        '>この内容で清算する</button></div>';
    }
    html += '</div>';

    // ── 過去の清算 ──
    var past = Settle.listSettlements(settlementsOf(currentGroup));
    html += '<div class="settle-section"><div class="settle-head">過去の清算</div>';
    if (past.length === 0) {
      html += '<div class="settle-sub">まだ清算の記録はありません。</div>';
    } else {
      // 新しい順なので、折りたたんでも最新の清算（取り消せる 1 件）は必ず出る
      var shown = showAllSettlements ? past : past.slice(0, PAST_LIMIT);
      var rest = past.length - shown.length;
      html += shown.map(function (s) {
        var transfers = Settle.transferList(s);
        var undoable = Settle.canUndo(settlementsOf(currentGroup), s.id);
        return '<div class="past-settlement' + (undoable ? '' : ' old') + '">' +
          '<div class="past-head">' +
            '<span class="past-date">' + esc(dateTime(s.createdAt)) + '</span>' +
            '<span class="past-count">対象 ' + Settle.targetCount(s) + ' 件</span>' +
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
              ' onchange="toggleTransferDone(\'' + s.id + '\', \'' + t.id + '\', this.checked)">' +
              // 打ち消し線は「A → B」（.transfer-pair）だけに付ける。印（.transfer-by）はその外に置く
              '<span class="transfer-names"><span class="transfer-pair">' +
              esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + '</span>' + mark + '</span>' +
              '<span class="transfer-amount">' + money(t.amount) + '</span></label>';
          }).join('') +
          '<div class="past-foot">' +
            (undoable
              ? '<button class="btn btn-secondary btn-sm" onclick="doUndoSettlement(\'' +
                s.id + '\')">この清算を取り消す</button>'
              : '<span class="past-note">取り消せるのは最新の清算のみです</span>') +
          '</div></div>';
      }).join('');
      if (rest > 0) {
        html += '<button class="btn btn-secondary btn-sm past-more" id="pastMoreBtn" ' +
          'onclick="showAllPastSettlements()">もっと見る（残り ' + rest + ' 件）</button>';
      }
    }
    html += '</div>';

    $('settlementContent').innerHTML = html;
  }

  /** 「もっと見る」: 過去の清算を全件出す（保存しないので開き直せば戻る） */
  function showAllPastSettlements() {
    showAllSettlements = true;
    renderSettlement();
  }

  /** 「この内容で清算する」 */
  function doConfirmSettlement() {
    if (!currentCode || !currentGroup) return;
    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    if (Settle.pickPending(pays).length) {
      toast('金額確認中の支払いがあります。先に金額を確定してください', 'error');
      return;
    }
    var me = Auth.user();
    var settlement = Settle.buildSettlement(members, pays, {
      uid: me ? me.uid : '', now: Date.now()
    });
    if (!settlement) { toast('清算する貸し借りがありません'); return; }

    var n = Object.keys(settlement.paymentIds).length;
    var m = Settle.transferList(settlement).length;
    if (!confirm('未清算の支払い ' + n + ' 件を清算として記録します。\n送金は ' + m +
      ' 本です。\n\n記録すると、この ' + n + ' 件は編集・削除できなくなります（取り消しは可能）。')) return;

    var btn = $('settleConfirmBtn');
    if (btn) { btn.disabled = true; btn.textContent = '記録中…'; }
    Store.confirmSettlement(currentCode, settlement).then(function () {
      toast('清算を記録しました');
      renderSettlement();
    }).catch(function (err) {
      if (btn) { btn.disabled = false; btn.textContent = 'この内容で清算する'; }
      fail('清算を記録できませんでした')(err);
    });
  }

  /** 送金 1 本のチェック（他の端末にもそのまま届く） */
  function toggleTransferDone(sid, tid, done) {
    if (!currentCode) return;
    Store.setTransferDone(currentCode, sid, tid, done)
      .catch(fail('送金のチェックを更新できませんでした'));
  }

  /** 清算の取り消し（最新の 1 件だけ） */
  function doUndoSettlement(sid) {
    if (!currentCode || !currentGroup) return;
    var all = settlementsOf(currentGroup);
    if (!Settle.canUndo(all, sid)) {
      toast('取り消せるのは最新の清算のみです', 'error');
      return;
    }
    var s = all[sid];
    if (!s) return;
    var n = Settle.targetCount(s);
    var msg = Settle.hasAnyDone(s)
      ? '送金チェックが入っています。本当にこの清算を取り消しますか？\n' +
        'チェックの記録も消えます（支払い ' + n + ' 件は未清算に戻ります）。'
      : 'この清算を取り消しますか？\n支払い ' + n + ' 件が未清算に戻ります。';
    if (!confirm(msg)) return;

    Store.undoSettlement(currentCode, sid, s.paymentIds || {}).then(function () {
      toast('清算を取り消しました');
      renderSettlement();
    }).catch(fail('清算を取り消せませんでした'));
  }

  // ---- CSV 出力（工事4a）----------------------------------------------

  /** v1 と同じやり方でファイルを落とす（Blob + a[download]） */
  function downloadCsv(text, filename) {
    var blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function groupNameForFile() {
    var n = currentGroup && currentGroup.meta && currentGroup.meta.name
      ? currentGroup.meta.name : 'グループ';
    return Csv.safeFileName(n);
  }

  /** 支払い一覧の CSV（本文とファイル名）。テストから中身を見られるように分けてある */
  function buildPaymentsCsv() {
    if (!currentGroup) return null;
    return {
      text: Csv.paymentsCsv(currentGroup, currentGroup.payments || {},
        currentGroup.settlements || {}),
      name: groupNameForFile() + '_支払い_' + Csv.stamp() + '.csv'
    };
  }

  /** 残高の CSV。いま画面に出ている表示（未清算のみ / 累計）で出す */
  function buildBalancesCsv() {
    if (!currentGroup) return null;
    return {
      text: Csv.balancesCsv(currentGroup, currentGroup.payments || {}, balanceMode),
      name: groupNameForFile() + '_残高_' + Csv.stamp() + '.csv'
    };
  }

  function openExportModal() {
    if (!currentGroup) return;
    $('exportBtns').innerHTML =
      '<button class="export-btn-row" onclick="exportPaymentsCsv()">' +
        '<span class="export-btn-icon">&#x1F4CB;</span>' +
        '<div><span class="export-btn-label">支払い一覧（CSV）</span>' +
        '<span class="export-btn-desc">日付・メモ・支払った人・金額・割り勘対象・1人あたり・清算状態</span>' +
        '</div></button>' +
      '<button class="export-btn-row" onclick="exportBalancesCsv()">' +
        '<span class="export-btn-icon">&#x1F4CA;</span>' +
        '<div><span class="export-btn-label">残高（CSV）</span>' +
        '<span class="export-btn-desc">メンバーごとの払った合計・負担分・残高</span>' +
        '</div></button>' +
      '<div class="export-note">残高 CSV は、いまの表示（<strong>' +
      (balanceMode === 'all' ? '累計' : '未清算のみ') + '</strong>）で出します。' +
      '切り替えたいときは、いったん閉じて残高の右上で切り替えてください。</div>';
    openModal('exportModal');
  }

  function exportPaymentsCsv() {
    var r = buildPaymentsCsv();
    if (!r) return null;
    downloadCsv(r.text, r.name);
    closeModal('exportModal');
    toast('支払い一覧を書き出しました: ' + r.name);
    return r;
  }

  function exportBalancesCsv() {
    var r = buildBalancesCsv();
    if (!r) return null;
    downloadCsv(r.text, r.name);
    closeModal('exportModal');
    toast('残高を書き出しました: ' + r.name);
    return r;
  }

  // ---- アプリ内ブラウザの案内（工事4a、§5.1）--------------------------

  /** LINE や Discord の中のブラウザなら案内を出す。ログインボタンは残したまま */
  function checkInAppBrowser() {
    var box = $('inAppNotice');
    if (!box || !Env) return false;
    var inApp = Env.isInAppBrowser(navigator.userAgent);
    box.hidden = !inApp;
    return inApp;
  }

  /** 開いている URL をコピー。できない環境では画面に出して手で選べるようにする */
  function copyPageUrl() {
    var url = location.href;
    var show = function () {
      var el = $('inAppUrl');
      if (el) { el.textContent = url; el.hidden = false; }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        var btn = $('btnCopyUrl');
        if (btn) {
          btn.textContent = 'コピーしました！';
          setTimeout(function () { btn.textContent = 'URL をコピー'; }, 1800);
        }
      }, show);
    } else {
      show();
    }
  }

  // ---- グループ設定 ---------------------------------------------------

  function openSettings() {
    if (!currentGroup) return;
    editMembers = memberList(currentGroup).map(function (m) {
      return { id: m.id, name: m.name, order: m.order, isNew: false };
    });
    $('editGroupName').value = currentGroup.meta && currentGroup.meta.name ? currentGroup.meta.name : '';
    $('editMemberInput').value = '';
    $('shareCodeBox').textContent = currentCode;
    renderEditMemberList();
    openModal('settingsModal');
  }

  function renderEditMemberList() {
    $('editMemberList').innerHTML = editMembers.map(function (m, i) {
      return '<div class="member-row">' +
        '<input class="form-input member-row-input" value="' + esc(m.name) + '" ' +
        'oninput="setEditMemberName(' + i + ', this.value)">' +
        '<button class="member-row-del" title="削除" onclick="removeEditMember(' + i + ')">&#x2715;</button>' +
        '</div>';
    }).join('');
  }
  function setEditMemberName(i, v) { if (editMembers[i]) editMembers[i].name = v; }
  function removeEditMember(i) {
    var m = editMembers[i];
    if (!m) return;
    if (!m.isNew && usedInPayments(m.id)) {
      if (!confirm('「' + m.name + '」には支払い記録があります。削除すると履歴の名前が「?」になります。削除しますか？')) return;
    }
    editMembers.splice(i, 1);
    renderEditMemberList();
  }
  function usedInPayments(mid) {
    return paymentList(currentGroup).some(function (p) {
      return p.payerId === mid || p.participants.indexOf(mid) >= 0;
    });
  }
  function addEditMember() {
    var el = $('editMemberInput');
    var name = el.value.trim();
    if (!name) return;
    editMembers.push({ id: null, name: name, order: editMembers.length, isNew: true });
    el.value = '';
    renderEditMemberList(); el.focus();
  }

  function saveSettings() {
    if (!currentCode || !currentGroup) return;
    var name = $('editGroupName').value.trim();
    if (!name) { alert('グループ名を入力してください'); return; }
    var cleaned = editMembers.filter(function (m) { return m.name.trim() !== ''; });
    if (cleaned.length < 2) { alert('メンバーを2人以上にしてください'); return; }

    var before = memberList(currentGroup);
    var jobs = [];

    if (!currentGroup.meta || currentGroup.meta.name !== name) {
      jobs.push(Store.setGroupName(currentCode, name));
    }
    cleaned.forEach(function (m, i) {
      var nm = m.name.trim();
      if (m.isNew || !m.id) {
        jobs.push(Store.addMember(currentCode, nm, i));
        return;
      }
      var old = before.filter(function (b) { return b.id === m.id; })[0];
      if (old && old.name !== nm) jobs.push(Store.renameMember(currentCode, m.id, nm));
    });
    before.forEach(function (b) {
      var still = cleaned.some(function (m) { return m.id === b.id; });
      if (!still) jobs.push(Store.removeMember(currentCode, b.id));
    });

    closeModal('settingsModal');
    Promise.all(jobs).catch(fail('設定を保存できませんでした'));
  }

  function copyShareCode() {
    var code = currentCode;
    if (!code) return;
    var done = function () {
      var el = $('shareCodeBox');
      el.textContent = 'コピーしました！';
      setTimeout(function () { el.textContent = code; }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, function () { toast('コピーできませんでした（手で選択してください）', 'error'); });
    } else {
      toast('この端末では自動コピーができません。コードを手で選択してください', 'error');
    }
  }

  function leaveGroup() {
    if (!currentCode) return;
    var name = currentGroup && currentGroup.meta ? currentGroup.meta.name : currentCode;
    if (!confirm('「' + name + '」から退出しますか？\n自分の一覧から消えるだけで、グループのデータは残ります。\n共有コードがあればまた参加できます。')) return;
    var code = currentCode;
    Store.stopWatchGroup();
    currentCode = null; currentGroup = null; seenPaymentAt = null;
    try { localStorage.removeItem(LS_LAST_GROUP); } catch (e) { /* noop */ }
    closeModal('settingsModal');
    render();
    Store.leaveGroup(code).then(function () { toast('退出しました'); })
      .catch(fail('退出できませんでした'));
  }

  function deleteGroup() {
    if (!currentCode) return;
    var name = currentGroup && currentGroup.meta ? currentGroup.meta.name : currentCode;
    if (!confirm('「' + name + '」を削除しますか？\nメンバー全員の画面から消え、支払い記録もすべて削除されます。\nこの操作は取り消せません。')) return;
    var code = currentCode;
    Store.stopWatchGroup();
    currentCode = null; currentGroup = null; seenPaymentAt = null;
    try { localStorage.removeItem(LS_LAST_GROUP); } catch (e) { /* noop */ }
    closeModal('settingsModal');
    render();
    Store.deleteGroup(code).then(function () { toast('グループを削除しました'); })
      .catch(fail('削除できませんでした'));
  }

  // ---- 接続状態 -------------------------------------------------------

  function setConnected(ok) {
    var dot = $('connDot');
    if (dot) {
      dot.classList.toggle('off', !ok);
      dot.title = ok ? 'オンライン（同期中）' : 'オフライン（再接続を待っています）';
    }
    // 画面上部の細い帯（§5.7）。書いた内容は SDK が再接続時に送る
    var banner = $('offlineBanner');
    if (banner) banner.hidden = !!ok;
  }

  // ---- 起動 -----------------------------------------------------------

  function start() {
    if (!root.KKFirebase || !root.KKFirebase.ready) {
      hideBoot();
      checkInAppBrowser();
      $('loginScreen').hidden = false;
      $('appLayout').hidden = true;
      var box = $('loginError');
      if (box) {
        box.textContent = 'Firebase を読み込めませんでした。通信環境を確認して再読み込みしてください。';
        box.hidden = false;
      }
      return;
    }

    checkInAppBrowser();

    document.querySelectorAll('.modal-overlay').forEach(function (ov) {
      ov.addEventListener('click', function (e) {
        if (e.target === ov) ov.classList.remove('open');
      });
    });

    // 書き込みの失敗は、どこから呼ばれたものでも必ずここでトーストになる（§5.7）
    Store.onWriteError(function (op, err) {
      toast(op + ': ' + errText(err), 'error');
    });

    Store.watchConnection(setConnected);

    Auth.onChange(function (user) {
      me = user;
      if (!user) {
        // 認証切れ（期限切れ・別端末でのログアウト）でもここに来る。
        // 監視を残すと権限エラーが出続けるので、必ず外す
        Store.stopWatchMyGroups();
        Store.stopWatchGroup();
        showLoggedOut();
        migrateCtx = null;
        closeModal('migrateModal');
        closeModal('migrateResultModal');
        myGroups = {}; metas = {};
        Object.keys(metaOff).forEach(function (c) { metaOff[c](); });
        metaOff = {};
        currentCode = null; currentGroup = null; seenPaymentAt = null;
        render();
        return;
      }
      showLoggedIn(user);
      Store.saveProfile(user).catch(function (e) { console.error('profile', e); });
      Store.watchMyGroups(function (groups) {
        myGroups = groups;
        syncMetaWatchers();
        renderSidebar();
        // 並べ替え（SortableJS）は #groupList に 1 回付ければ、描き直しても効き続ける
        if (!groupOrderAttached) {
          groupOrderAttached = true;
          GroupOrder.attach($('groupList'), saveGroupOrder);
        }
        // 前回開いていたグループを復元する
        if (!currentCode) {
          var last = null;
          try { last = localStorage.getItem(LS_LAST_GROUP); } catch (e) { last = null; }
          if (last && myGroups[last]) selectGroup(last);
          else renderMain();
        } else if (!myGroups[currentCode]) {
          // 退出などで一覧から消えた
          Store.stopWatchGroup();
          currentCode = null; currentGroup = null; seenPaymentAt = null;
          render();
        }
      }, fail('グループ一覧を読み込めませんでした'));
      render();
    });

    render();
  }

  // ---- index.html の onclick から呼ぶものを global に置く ---------------

  root.KKUI = { toast: toast, render: render };

  root.openModal = openModal;
  root.closeModal = closeModal;
  root.toggleSidebar = toggleSidebar;
  root.closeSidebar = closeSidebar;
  root.doLogin = doLogin;
  root.doLogout = doLogout;
  root.selectGroup = selectGroup;
  root.dismissMissingGroup = dismissMissingGroup;
  root.openNewGroupModal = openNewGroupModal;
  root.renderNewMemberList = renderNewMemberList;
  root.addNewMember = addNewMember;
  root.removeNewMember = removeNewMember;
  root.createGroup = createGroup;
  root.openJoinModal = openJoinModal;
  root.doJoin = doJoin;
  root.confirmMigrate = confirmMigrate;
  root.cancelMigrate = cancelMigrate;
  root.closeMigrateResult = closeMigrateResult;
  root.copyCode = copyCode;
  root.openPaymentModal = openPaymentModal;
  root.openEditPayModal = openEditPayModal;
  root.toggleChip = toggleChip;
  root.recordPayment = recordPayment;
  root.deletePay = deletePay;
  root.openSettlement = openSettlement;
  root.doConfirmSettlement = doConfirmSettlement;
  root.toggleTransferDone = toggleTransferDone;
  root.doUndoSettlement = doUndoSettlement;
  root.showAllPastSettlements = showAllPastSettlements;
  root.setBalanceMode = setBalanceMode;
  root.lockedNotice = lockedNotice;
  root.onPendingToggle = onPendingToggle;
  root.openExportModal = openExportModal;
  root.exportPaymentsCsv = exportPaymentsCsv;
  root.exportBalancesCsv = exportBalancesCsv;
  root.buildPaymentsCsv = buildPaymentsCsv;
  root.buildBalancesCsv = buildBalancesCsv;
  root.copyPageUrl = copyPageUrl;
  root.checkInAppBrowser = checkInAppBrowser;
  root.openSettings = openSettings;
  root.renderEditMemberList = renderEditMemberList;
  root.setEditMemberName = setEditMemberName;
  root.addEditMember = addEditMember;
  root.removeEditMember = removeEditMember;
  root.saveSettings = saveSettings;
  root.copyShareCode = copyShareCode;
  root.leaveGroup = leaveGroup;
  root.deleteGroup = deleteGroup;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})(window);
