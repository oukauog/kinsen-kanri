/*
 * store.js — Realtime Database への読み書き（仕様書 §3 のデータモデル）
 *
 *   users/{uid}/profile            : { displayName, photoURL, updatedAt }
 *   users/{uid}/groups/{code}      : { joinedAt }            ← 左サイドバーの元
 *   groups/{code}/meta             : { name, createdAt, createdBy, schemaVersion }
 *   groups/{code}/members/{mid}    : { name, order }
 *   groups/{code}/payments/{pid}   : { date, memo, payerId, amount,
 *                                      participants:{mid:true}, settlementId, pending,
 *                                      createdBy, createdAt, updatedAt }
 *
 * 決めごと:
 *   ・配列は使わない。すべて ID キーのオブジェクト
 *   ・書き込みは変更したノードだけ（set / update / remove）。全置換はしない
 *   ・清算レコード（settlements）は工事3。ここでは settlementId: null、pending: false を
 *     今から書いておくだけ
 *   ・セキュリティルールの都合上、グループ作成・参加はどちらも
 *     「先に users/{uid}/groups/{code} を書いてから groups/{code} を触る」順序が必須
 *   ・旧パス rooms/{code} は「コードで参加したとき 1 回だけ読む」以外に触らない。
 *     書き込みは禁止（友人の実データ。工事2 の移行でも読むだけ）
 *   ・書き込みは wrapWrite で包み、失敗を必ず onWriteError に通す（§5.7）
 */
(function (root) {
  'use strict';

  var FB = root.KKFirebase;

  // ---- ID 生成 --------------------------------------------------------

  var CODE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

  /** 共有コード: 6 桁の英数大文字（v1 と同じ桁数・文字種） */
  function randomCode() {
    var s = '';
    for (var i = 0; i < 6; i++) {
      s += CODE_CHARS.charAt(Math.floor(Math.random() * CODE_CHARS.length));
    }
    return s;
  }

  /** メンバー ID など、グループ内で一意ならよい ID（v1 の uid() と同じ作り） */
  function localId() {
    return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function requireReady() {
    if (!FB || !FB.ready) throw new Error('Firebase が初期化できていません');
  }

  function uid() {
    var u = FB && FB.ready ? FB.auth.currentUser : null;
    if (!u) throw new Error('ログインしていません');
    return u.uid;
  }

  function ref(path) { requireReady(); return FB.db.ref(path); }

  // ---- 書き込みエラーの拾い上げ（§5.7）--------------------------------

  var writeErrorHandler = null;

  /** 書き込みが失敗したときに呼ばれる関数を登録する（ui.js がトーストを出す） */
  function onWriteError(fn) { writeErrorHandler = fn; }

  /**
   * 書き込みの Promise を包んで、失敗を必ず 1 か所に通す。
   * 呼び出し側の .catch もそのまま動くように、エラーは再送出する。
   * 二重にトーストしないよう、通知済みの印を付ける。
   * @param {string} op 失敗したときに出す日本語の操作名
   */
  function wrapWrite(op, p) {
    return p.catch(function (err) {
      if (err && !err.__kkReported) {
        err.__kkReported = true;
        if (writeErrorHandler) {
          try { writeErrorHandler(op, err); } catch (e) { console.error(e); }
        } else {
          console.error(op, err);
        }
      }
      throw err;
    });
  }

  // ---- プロフィール ---------------------------------------------------

  function saveProfile(user) {
    if (!user) return Promise.resolve();
    return wrapWrite('プロフィールを保存できませんでした',
      ref('users/' + user.uid + '/profile').set({
        displayName: user.displayName || '',
        photoURL: user.photoURL || '',
        updatedAt: FB.now()
      }));
  }

  // ---- 参加グループ一覧 -----------------------------------------------

  var myGroupsRef = null;
  var myGroupsCb = null;

  /**
   * users/{uid}/groups を監視する。cb には { code: {joinedAt} } が渡る。
   * 監視は 1 本だけ。呼び直すと前の監視は外れる。
   */
  function watchMyGroups(cb, onError) {
    stopWatchMyGroups();
    myGroupsRef = ref('users/' + uid() + '/groups');
    myGroupsCb = function (snap) { cb(snap.val() || {}); };
    myGroupsRef.on('value', myGroupsCb, onError || function (e) { console.error(e); });
  }

  function stopWatchMyGroups() {
    if (myGroupsRef && myGroupsCb) myGroupsRef.off('value', myGroupsCb);
    myGroupsRef = null; myGroupsCb = null;
  }

  // ---- グループ本体の監視 ---------------------------------------------

  var groupRef = null;
  var groupCb = null;

  /**
   * groups/{code} を丸ごと監視する。cb には { meta, members, payments } が渡る。
   * 1 グループ分（支払い数百件）なら value 監視で十分軽い。
   * 件数が増えて重くなったら child_added / child_changed に分ける（申し送り）。
   */
  function watchGroup(code, cb, onError) {
    stopWatchGroup();
    groupRef = ref('groups/' + code);
    groupCb = function (snap) { cb(snap.val() || null); };
    groupRef.on('value', groupCb, onError || function (e) { console.error(e); });
  }

  function stopWatchGroup() {
    if (groupRef && groupCb) groupRef.off('value', groupCb);
    groupRef = null; groupCb = null;
  }

  // ---- グループの作成・参加・退出・削除 -------------------------------

  /** groups/{code}/meta を 1 回だけ読む（ルール上、ログイン済みなら誰でも読める） */
  function readMeta(code) {
    return ref('groups/' + code + '/meta').once('value').then(function (s) { return s.val(); });
  }

  /**
   * groups/{code}/meta を監視する（サイドバーの名前をリアルタイムにするため）。
   * @returns {Function} 監視を外す関数
   */
  function watchMeta(code, cb, onError) {
    var r = ref('groups/' + code + '/meta');
    var h = function (snap) { cb(snap.val()); };
    r.on('value', h, onError || function (e) { console.error(e); });
    return function () { r.off('value', h); };
  }

  /** 未使用の共有コードを探す（最大 10 回）*/
  function findFreeCode(tries) {
    var n = tries == null ? 10 : tries;
    var code = randomCode();
    return readMeta(code).then(function (meta) {
      if (!meta) return code;
      if (n <= 1) throw new Error('共有コードを発行できませんでした。もう一度お試しください');
      return findFreeCode(n - 1);
    });
  }

  /**
   * グループを作る。
   * @param {string} name グループ名
   * @param {string[]} memberNames メンバー名（2 人以上）
   * @returns {Promise<string>} 共有コード
   */
  function createGroup(name, memberNames) {
    var myUid = uid();
    return findFreeCode().then(function (code) {
      var members = {};
      memberNames.forEach(function (n, i) {
        members[localId()] = { name: n, order: i };
      });
      // ルールが「自分の一覧に入っていること」を要求するので、先に自分を登録する
      return wrapWrite('グループを作成できませんでした',
        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () {
          return ref('groups/' + code).update({
            meta: {
              name: name,
              createdAt: FB.now(),
              createdBy: myUid,
              schemaVersion: 2
            },
            members: members
          });
        }))
        .then(function () { return code; });
    });
  }

  /**
   * 共有コードで参加する。meta が無ければ何もせずエラー。
   * @returns {Promise<Object>} meta
   */
  function joinGroup(code) {
    var myUid = uid();
    return readMeta(code).then(function (meta) {
      if (!meta) throw new Error('そのコードのグループは見つかりませんでした');
      return wrapWrite('グループに参加できませんでした',
        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() }))
        .then(function () { return meta; });
    });
  }

  /** 自分の一覧から外すだけ。グループのデータは残る */
  function leaveGroup(code) {
    return wrapWrite('退出できませんでした',
      ref('users/' + uid() + '/groups/' + code).remove());
  }

  /**
   * グループを削除する。groups/{code} を消してから自分の一覧から外す
   * （順序が逆だと、ルールで groups/{code} への書き込み権限を失って消せなくなる）。
   * 他のメンバーの users/{uid}/groups/{code} は消せない（権限が無い）ので、
   * 相手の画面では「（削除されたグループ）」として残る。ui.js で片付けられるようにしてある。
   */
  function deleteGroup(code) {
    var myUid = uid();
    return wrapWrite('グループを削除できませんでした',
      ref('groups/' + code).remove()
        .then(function () { return ref('users/' + myUid + '/groups/' + code).remove(); }));
  }

  // ---- グループの中身 -------------------------------------------------

  function setGroupName(code, name) {
    return wrapWrite('グループ名を変更できませんでした',
      ref('groups/' + code + '/meta/name').set(name));
  }

  /** メンバー追加。@returns {Promise<string>} 追加したメンバー ID */
  function addMember(code, name, order) {
    var mid = localId();
    return wrapWrite('メンバーを追加できませんでした',
      ref('groups/' + code + '/members/' + mid).set({ name: name, order: order }))
      .then(function () { return mid; });
  }

  function renameMember(code, mid, name) {
    return wrapWrite('メンバー名を変更できませんでした',
      ref('groups/' + code + '/members/' + mid + '/name').set(name));
  }

  function removeMember(code, mid) {
    return wrapWrite('メンバーを削除できませんでした',
      ref('groups/' + code + '/members/' + mid).remove());
  }

  /**
   * 支払いの新規作成。
   * @param {Object} p { date, memo, payerId, amount, participants: {mid:true} }
   * @returns {Promise<string>} 支払い ID
   */
  function addPayment(code, p) {
    var myUid = uid();
    var pid = ref('groups/' + code + '/payments').push().key;
    return wrapWrite('支払いを記録できませんでした',
      ref('groups/' + code + '/payments/' + pid).set({
      date: p.date,
      memo: p.memo || '',
      payerId: p.payerId,
      amount: p.amount,
      participants: p.participants,
      settlementId: null,   // 工事3 の清算レコード用。今は必ず null
      pending: false,       // 工事3 の「金額確認中」用。今は必ず false
      createdBy: myUid,
      createdAt: FB.now(),
      updatedAt: FB.now()
      })).then(function () { return pid; });
  }

  /** 支払いの更新。触ったフィールドだけ update する（createdBy / createdAt は保つ） */
  function updatePayment(code, pid, p) {
    return wrapWrite('支払いを更新できませんでした',
      ref('groups/' + code + '/payments/' + pid).update({
        date: p.date,
        memo: p.memo || '',
        payerId: p.payerId,
        amount: p.amount,
        participants: p.participants,
        updatedAt: FB.now()
      }));
  }

  function removePayment(code, pid) {
    return wrapWrite('支払いを削除できませんでした',
      ref('groups/' + code + '/payments/' + pid).remove());
  }

  // ---- 移行（旧 rooms からの取り込み。工事2）--------------------------

  /**
   * 旧ルームを 1 回だけ読む。**読み取り専用**。ここでも他のどこでも rooms/ には書かない。
   * @returns {Promise<Object|null>} 旧ルームの中身（無ければ null）
   */
  function readRoom(code) {
    return ref('rooms/' + code).once('value').then(function (s) { return s.val(); });
  }

  /**
   * 重複しない新しい共有コードを n 個発行する（既存の findFreeCode を使う）。
   * @returns {Promise<string[]>}
   */
  function allocCodes(n, acc) {
    var got = acc || [];
    if (got.length >= n) return Promise.resolve(got);
    return findFreeCode().then(function (code) {
      if (got.indexOf(code) >= 0) return allocCodes(n, got);   // まず起きないが念のため
      got.push(code);
      return allocCodes(n, got);
    });
  }

  /**
   * 変換済みデータ（Migrate.convertRoom の戻り値）を書き込む。
   *
   * 手順（ルールの都合でこの順序でないと書けない）:
   *   1. users/{uid}/groups/{code} を登録（自分の一覧に入れる＝グループへの書き込み権限を得る）
   *   2. groups/{code}/meta を transaction で「まだ無いときだけ」書く
   *      → 誰かが先に移行していたら、そのグループは書かずに「参加しただけ」にする
   *   3. meta を書けたグループにだけ members / payments を update で書く
   *
   * 途中で失敗したら、この呼び出しで足した users/{uid}/groups/{code} を取り消して
   * 中途半端な状態を残さない（rooms/ には最初から何も書かない）。
   *
   * @param {Object} converted { groups: { code: {meta, members, payments} }, order: [code] }
   * @returns {Promise<Object>} { migrated: [code], already: [code] }
   *   already = 先に誰かが移行していたので中身は書かなかったコード
   */
  function migrateRoom(converted) {
    var myUid = uid();
    var codes = (converted && converted.order && converted.order.length)
      ? converted.order.slice()
      : Object.keys((converted && converted.groups) || {});
    if (codes.length === 0) return Promise.resolve({ migrated: [], already: [] });

    var addedByMe = [];      // 失敗したときに取り消す対象
    var migrated = [];
    var already = [];

    function rollback() {
      return Promise.all(addedByMe.map(function (code) {
        return ref('users/' + myUid + '/groups/' + code).remove().catch(function () { });
      }));
    }

    // 1. 自分の一覧に登録（もともと入っていたものは取り消し対象にしない）
    function joinAll(i) {
      if (i >= codes.length) return Promise.resolve();
      var code = codes[i];
      var myRef = ref('users/' + myUid + '/groups/' + code);
      return myRef.once('value').then(function (s) {
        if (s.exists()) return null;
        return myRef.set({ joinedAt: FB.now() }).then(function () { addedByMe.push(code); });
      }).then(function () { return joinAll(i + 1); });
    }

    // 2〜3. meta を取り合いしてから中身を書く
    function writeAll(i) {
      if (i >= codes.length) return Promise.resolve();
      var code = codes[i];
      var g = converted.groups[code];
      return ref('groups/' + code + '/meta').transaction(function (current) {
        if (current === null) return g.meta;
        return undefined;      // すでにある → 何もしない（二重移行の防止）
      }).then(function (res) {
        if (!res.committed) { already.push(code); return null; }
        return ref('groups/' + code).update({
          members: g.members || {},
          payments: g.payments || {}
        }).then(function () { migrated.push(code); });
      }).then(function () { return writeAll(i + 1); });
    }

    return wrapWrite('取り込みに失敗しました',
      joinAll(0).then(function () { return writeAll(0); })
        .then(function () { return { migrated: migrated, already: already }; })
        .catch(function (err) {
          return rollback().then(function () { throw err; });
        }));
  }

  // ---- 接続状態 -------------------------------------------------------

  /** .info/connected を監視する（cb に true / false） */
  function watchConnection(cb) {
    requireReady();
    FB.db.ref('.info/connected').on('value', function (snap) { cb(snap.val() === true); });
  }

  root.KKStore = {
    randomCode: randomCode,
    localId: localId,
    saveProfile: saveProfile,
    watchMyGroups: watchMyGroups,
    stopWatchMyGroups: stopWatchMyGroups,
    watchGroup: watchGroup,
    stopWatchGroup: stopWatchGroup,
    readMeta: readMeta,
    watchMeta: watchMeta,
    createGroup: createGroup,
    joinGroup: joinGroup,
    leaveGroup: leaveGroup,
    deleteGroup: deleteGroup,
    setGroupName: setGroupName,
    addMember: addMember,
    renameMember: renameMember,
    removeMember: removeMember,
    addPayment: addPayment,
    updatePayment: updatePayment,
    removePayment: removePayment,
    readRoom: readRoom,
    allocCodes: allocCodes,
    migrateRoom: migrateRoom,
    onWriteError: onWriteError,
    watchConnection: watchConnection
  };
})(window);
