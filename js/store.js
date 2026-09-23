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

  // ---- プロフィール ---------------------------------------------------

  function saveProfile(user) {
    if (!user) return Promise.resolve();
    return ref('users/' + user.uid + '/profile').set({
      displayName: user.displayName || '',
      photoURL: user.photoURL || '',
      updatedAt: FB.now()
    });
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
      return ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
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
        })
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
      return ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () { return meta; });
    });
  }

  /** 自分の一覧から外すだけ。グループのデータは残る */
  function leaveGroup(code) {
    return ref('users/' + uid() + '/groups/' + code).remove();
  }

  /**
   * グループを削除する。groups/{code} を消してから自分の一覧から外す
   * （順序が逆だと、ルールで groups/{code} への書き込み権限を失って消せなくなる）。
   * 他のメンバーの users/{uid}/groups/{code} は消せない（権限が無い）ので、
   * 相手の画面では「（削除されたグループ）」として残る。ui.js で片付けられるようにしてある。
   */
  function deleteGroup(code) {
    var myUid = uid();
    return ref('groups/' + code).remove()
      .then(function () { return ref('users/' + myUid + '/groups/' + code).remove(); });
  }

  // ---- グループの中身 -------------------------------------------------

  function setGroupName(code, name) {
    return ref('groups/' + code + '/meta/name').set(name);
  }

  /** メンバー追加。@returns {Promise<string>} 追加したメンバー ID */
  function addMember(code, name, order) {
    var mid = localId();
    return ref('groups/' + code + '/members/' + mid)
      .set({ name: name, order: order })
      .then(function () { return mid; });
  }

  function renameMember(code, mid, name) {
    return ref('groups/' + code + '/members/' + mid + '/name').set(name);
  }

  function removeMember(code, mid) {
    return ref('groups/' + code + '/members/' + mid).remove();
  }

  /**
   * 支払いの新規作成。
   * @param {Object} p { date, memo, payerId, amount, participants: {mid:true} }
   * @returns {Promise<string>} 支払い ID
   */
  function addPayment(code, p) {
    var myUid = uid();
    var pid = ref('groups/' + code + '/payments').push().key;
    return ref('groups/' + code + '/payments/' + pid).set({
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
    }).then(function () { return pid; });
  }

  /** 支払いの更新。触ったフィールドだけ update する（createdBy / createdAt は保つ） */
  function updatePayment(code, pid, p) {
    return ref('groups/' + code + '/payments/' + pid).update({
      date: p.date,
      memo: p.memo || '',
      payerId: p.payerId,
      amount: p.amount,
      participants: p.participants,
      updatedAt: FB.now()
    });
  }

  function removePayment(code, pid) {
    return ref('groups/' + code + '/payments/' + pid).remove();
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
    watchConnection: watchConnection
  };
})(window);
