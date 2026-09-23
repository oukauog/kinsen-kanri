/*
 * tests/ui_smoke_fakes.js — ui.js を Firebase 抜きで動かすための差し替え
 *
 * KKFirebase / KKStore / KKAuth を、同じ形のメモリ実装に置き換える。
 * これで「ログインしてグループを作って支払いを入れる」画面まわりを
 * ブラウザ無人（ヘッドレス）で一通り動かせる。
 * 本番の index.html からは読み込まれない（tools/make_uitest.py が作る
 * 確認用ページからのみ読み込む）。
 */
(function (root) {
  'use strict';

  var data = { users: {}, groups: {} };
  var rooms = {};                 // 旧バージョンのルーム（工事2 の移行確認用）
  var connCb = null;              // watchConnection のコールバック
  var writeErrCb = null;          // onWriteError のコールバック
  var failNext = false;           // 次の書き込みをわざと失敗させる
  var watchers = { myGroups: null, group: {}, meta: {} };
  var USER = { uid: 'u-test', displayName: 'テスト太郎', photoURL: '', email: 't@example.com' };

  function clone(o) { return JSON.parse(JSON.stringify(o == null ? null : o)); }
  function later(fn) { setTimeout(fn, 0); }

  function notifyMyGroups() {
    if (watchers.myGroups) {
      var g = (data.users[USER.uid] && data.users[USER.uid].groups) || {};
      later(function () { watchers.myGroups(clone(g)); });
    }
  }
  function notifyGroup(code) {
    if (watchers.group[code]) later(function () { watchers.group[code](clone(data.groups[code] || null)); });
    if (watchers.meta[code]) {
      later(function () {
        var g = data.groups[code];
        watchers.meta[code](g && g.meta ? clone(g.meta) : null);
      });
    }
  }

  var id = 0;
  function nextId(p) { id++; return p + id; }

  // store.js の ifNotSettled と同じふるまい（清算済みは書かずに拒否）
  function reportLocked(op) {
    var err = new Error('清算済みの支払いは編集できません。先に清算を取り消してください');
    err.code = 'KK_SETTLED_LOCKED';
    err.__kkReported = true;
    if (writeErrCb) writeErrCb(op, err);
    return Promise.reject(err);
  }

  // store.js の wrapWrite と同じふるまい: 通知して、印を付けて、拒否する
  function reportFail(op) {
    var err = new Error('テストのための失敗');
    err.code = 'PERMISSION_DENIED';
    err.__kkReported = true;
    if (writeErrCb) writeErrCb(op, err);
    return Promise.reject(err);
  }

  root.KKFirebase = { ready: true, error: null, now: function () { return Date.now(); } };

  root.KKAuth = {
    _handlers: [],
    onChange: function (fn) { this._handlers.push(fn); },
    login: function () { return Promise.resolve(); },
    logout: function () {
      var hs = this._handlers;
      later(function () { hs.forEach(function (f) { f(null); }); });
      return Promise.resolve();
    },
    user: function () { return USER; },
    _signIn: function () {
      var hs = this._handlers;
      hs.forEach(function (f) { f(USER); });
    }
  };

  root.KKStore = {
    _data: data,
    localId: function () { return nextId('m'); },
    randomCode: function () { return 'TEST' + (10 + (id++)); },
    saveProfile: function () { return Promise.resolve(); },

    watchMyGroups: function (cb) { watchers.myGroups = cb; notifyMyGroups(); },
    stopWatchMyGroups: function () { watchers.myGroups = null; },
    watchGroup: function (code, cb) { watchers.group[code] = cb; notifyGroup(code); },
    stopWatchGroup: function () { watchers.group = {}; },
    watchMeta: function (code, cb) {
      watchers.meta[code] = cb;
      notifyGroup(code);
      return function () { delete watchers.meta[code]; };
    },
    readMeta: function (code) {
      var g = data.groups[code];
      return Promise.resolve(g && g.meta ? clone(g.meta) : null);
    },
    createGroup: function (name, names) {
      var code = this.randomCode();
      var members = {};
      names.forEach(function (n, i) { members[nextId('m')] = { name: n, order: i }; });
      data.groups[code] = { meta: { name: name, createdAt: Date.now(), createdBy: USER.uid, schemaVersion: 2 }, members: members };
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      data.users[USER.uid].groups[code] = { joinedAt: Date.now() };
      notifyMyGroups(); notifyGroup(code);
      return Promise.resolve(code);
    },
    joinGroup: function (code) {
      var g = data.groups[code];
      if (!g) return Promise.reject(new Error('見つかりません'));
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      data.users[USER.uid].groups[code] = { joinedAt: Date.now() };
      notifyMyGroups();
      return Promise.resolve(clone(g.meta));
    },
    leaveGroup: function (code) {
      if (data.users[USER.uid]) delete data.users[USER.uid].groups[code];
      notifyMyGroups();
      return Promise.resolve();
    },
    deleteGroup: function (code) {
      delete data.groups[code];
      if (data.users[USER.uid]) delete data.users[USER.uid].groups[code];
      notifyGroup(code); notifyMyGroups();
      return Promise.resolve();
    },
    setGroupName: function (code, name) {
      data.groups[code].meta.name = name; notifyGroup(code); return Promise.resolve();
    },
    addMember: function (code, name, order) {
      var mid = nextId('m');
      data.groups[code].members = data.groups[code].members || {};
      data.groups[code].members[mid] = { name: name, order: order };
      notifyGroup(code); return Promise.resolve(mid);
    },
    renameMember: function (code, mid, name) {
      data.groups[code].members[mid].name = name; notifyGroup(code); return Promise.resolve();
    },
    removeMember: function (code, mid) {
      delete data.groups[code].members[mid]; notifyGroup(code); return Promise.resolve();
    },
    addPayment: function (code, p) {
      if (failNext) { failNext = false; return reportFail('支払いを記録できませんでした'); }
      var pid = nextId('p');
      data.groups[code].payments = data.groups[code].payments || {};
      var pending = p.pending === true;
      data.groups[code].payments[pid] = {
        date: p.date, memo: p.memo || '', payerId: p.payerId,
        amount: pending ? 0 : p.amount,
        participants: p.participants, settlementId: null, pending: pending,
        createdBy: USER.uid, createdAt: Date.now(), updatedAt: Date.now()
      };
      notifyGroup(code); return Promise.resolve(pid);
    },
    updatePayment: function (code, pid, p) {
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
    },
    watchConnection: function (cb) { connCb = cb; later(function () { cb(true); }); },
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
    },

    // ほかの端末からの変更を模擬する（リアルタイム反映の確認用）
    _remoteAddPayment: function (code, p) {
      return root.KKStore.addPayment(code, p);
    },
    _setConnected: function (ok) { if (connCb) connCb(ok); },
    _failNextWrite: function () { failNext = true; },
    _seedRoom: function (code, room) { rooms[code] = room; },
    _seedGroup: function (code, name, memberNames) {
      var members = {};
      memberNames.forEach(function (n, i) { members[nextId('m')] = { name: n, order: i }; });
      data.groups[code] = { meta: { name: name, createdAt: 1, createdBy: 'someone', schemaVersion: 2 }, members: members };
    }
  };
})(window);
