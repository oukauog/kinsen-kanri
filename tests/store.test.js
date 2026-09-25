/*
 * tests/store.test.js — js/store.js の書き込み（パスとキー）の固定テスト（工事6）
 * 実行: node tests/store.test.js（まとめては node tests/run_all.js）
 *
 * ここが通る = 「store.js がどのパスに、どの操作（set / update / remove）で、
 * どのキーと値を書くか」が工事6 の時点のまま。store.js の書き込みを変える工事では、
 * 先にこのテストを現状で通し、変更後に期待値を直す。
 *
 * js/store.js は変更しない。末尾が })(window); なので、require の前に
 *   global.KKFirebase = 偽の Firebase
 *   global.window = global
 * を用意する。store.js は読み込んだ時点の KKFirebase を掴むので、
 * 以後はこのオブジェクトの中身（ready / auth.currentUser）を書き換えて状態を切り替える。
 *
 * このテストは「現状を固定する」もの。あるべき姿ではなく、今の書き方をそのまま期待値にしている。
 * migrateRoom / allocCodes / readRoom は対象外。
 */
'use strict';

const assert = require('assert');

// ---- 偽の Firebase ---------------------------------------------------

const NOW = '__SERVER_TIMESTAMP__';   // FB.now() の目印（本物は ServerValue.TIMESTAMP）
const USER = { uid: 'U1', displayName: 'テスト太郎', email: 'taro@example.com' };

const state = {
  writes: [],     // { op: 'set' | 'update' | 'remove' | 'transaction', path, value }
  seed: {},       // once('value') / transaction が読む値。{ path: 値 }（祖先の path に置いた値の中も引ける）
  fail: {},       // { path: err } この path への set / update / remove を reject する
  listens: [],    // on / off の記録
  pushN: 0
};

/** undefined のキーも残す深いコピー（JSON だとキーの過不足が見えなくなるため） */
function copy(v) {
  if (v === null || typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map(copy);
  const o = {};
  Object.keys(v).forEach(k => { o[k] = copy(v[k]); });
  return o;
}

/** seed から path の値を引く。ぴったりの key が無ければ、いちばん近い祖先の値の中をたどる */
function readSeed(path) {
  if (Object.prototype.hasOwnProperty.call(state.seed, path)) return copy(state.seed[path]);
  let best = null;
  Object.keys(state.seed).forEach(k => {
    if (path.indexOf(k + '/') === 0 && (best === null || k.length > best.length)) best = k;
  });
  if (best === null) return null;
  let v = state.seed[best];
  path.slice(best.length + 1).split('/').forEach(part => {
    v = (v == null || typeof v !== 'object') ? undefined : v[part];
  });
  return v === undefined ? null : copy(v);
}

function snapshot(v) {
  return { val: () => v, exists: () => v != null };
}

function fakeRef(path) {
  function write(op, value) {
    state.writes.push({ op: op, path: path, value: copy(value) });
    if (Object.prototype.hasOwnProperty.call(state.fail, path)) return Promise.reject(state.fail[path]);
    return Promise.resolve();
  }
  return {
    key: path.split('/').pop(),
    set: v => write('set', v),
    update: v => write('update', v),
    remove: () => write('remove', undefined),
    once: () => Promise.resolve(snapshot(readSeed(path))),
    push: () => {
      state.pushN++;
      return fakeRef(path + '/P' + state.pushN);
    },
    transaction: fn => {
      const cur = readSeed(path);
      const next = fn(cur);
      if (next === undefined) return Promise.resolve({ committed: false, snapshot: snapshot(cur) });
      state.writes.push({ op: 'transaction', path: path, value: copy(next) });
      state.seed[path] = copy(next);
      return Promise.resolve({ committed: true, snapshot: snapshot(next) });
    },
    on: (ev, cb) => { state.listens.push({ op: 'on', path: path, event: ev, cb: cb }); },
    off: (ev, cb) => { state.listens.push({ op: 'off', path: path, event: ev, cb: cb }); }
  };
}

const FB = {
  ready: true,
  error: null,
  auth: { currentUser: Object.assign({}, USER) },
  db: { ref: fakeRef },
  now: () => NOW
};

global.KKFirebase = FB;
global.window = global;
require('../js/store.js');
const S = global.KKStore;
const Settle = require('../js/settle.js');

function reset() {
  state.writes = [];
  state.seed = {};
  state.fail = {};
  state.listens = [];
  state.pushN = 0;
  FB.ready = true;
  FB.auth.currentUser = Object.assign({}, USER);
  S.onWriteError(null);
}

/** 書き込みの記録（op / path / value）だけを取り出す */
function writes() { return state.writes.map(w => ({ op: w.op, path: w.path, value: w.value })); }

/** onWriteError に登録して、呼ばれ方を記録する */
function recordWriteErrors() {
  const calls = [];
  S.onWriteError((op, err) => { calls.push({ op: op, err: err }); });
  return calls;
}

/**
 * fn が失敗するまでを見る。同期で throw したか、Promise が reject したかも返す。
 * 成功してしまったら assert で落とす。
 */
async function failure(fn) {
  let p;
  try {
    p = fn();
  } catch (e) {
    return { sync: true, err: e };
  }
  try {
    await p;
  } catch (e) {
    return { sync: false, err: e };
  }
  assert.fail('失敗するはずが成功した');
}

// ---- テストの入れ物（Promise を返してよい。順番に await して最後に集計する）----

const tests = [];
function test(name, fn) { tests.push({ name: name, fn: fn }); }

// =====================================================================
// 1. createGroup
// =====================================================================

test('1 createGroup: users/U1/groups/<code> の set → groups/<code> の update の順に 2 件だけ書く', async () => {
  const code = await S.createGroup('テスト', ['あ', 'い'], 5);
  assert.match(code, /^[A-Z0-9]{6}$/);
  const w = writes();
  assert.strictEqual(w.length, 2, JSON.stringify(w));
  assert.deepStrictEqual([w[0].op, w[0].path], ['set', 'users/U1/groups/' + code]);
  assert.deepStrictEqual([w[1].op, w[1].path], ['update', 'groups/' + code]);
});

test('1 createGroup: users 側は { joinedAt: NOW, order: 5 }', async () => {
  const code = await S.createGroup('テスト', ['あ', 'い'], 5);
  assert.deepStrictEqual(writes()[0].value, { joinedAt: NOW, order: 5 });
  assert.strictEqual(writes()[0].path, 'users/U1/groups/' + code);
});

test('1 createGroup: groups 側の update は meta と members だけ（order は書かない）', async () => {
  await S.createGroup('テスト', ['あ', 'い'], 5);
  const v = writes()[1].value;
  assert.deepStrictEqual(Object.keys(v).sort(), ['members', 'meta']);
  assert.ok(!('order' in v));
  assert.deepStrictEqual(v.meta, { name: 'テスト', createdAt: NOW, createdBy: 'U1', schemaVersion: 2 });
  const ms = Object.keys(v.members).map(k => v.members[k]).sort((a, b) => a.order - b.order);
  assert.deepStrictEqual(ms, [{ name: 'あ', order: 0 }, { name: 'い', order: 1 }]);
  Object.keys(v.members).forEach(k => assert.match(k, /^[0-9a-z]+$/, 'メンバー ID ' + k));
});

test('1 createGroup: order を渡さなければ users 側は { joinedAt } だけ', async () => {
  await S.createGroup('テスト', ['あ', 'い']);
  assert.deepStrictEqual(writes()[0].value, { joinedAt: NOW });
});

// =====================================================================
// 2. joinGroup
// =====================================================================

test('2 joinGroup: meta が無ければ reject（そのコードのグループは見つかりませんでした）で書き込み 0 件', async () => {
  const f = await failure(() => S.joinGroup('NOPE00', 7));
  assert.strictEqual(f.sync, false);
  assert.strictEqual(f.err.message, 'そのコードのグループは見つかりませんでした');
  assert.strictEqual(state.writes.length, 0);
});

test('2 joinGroup: order 7 → users/U1/groups/<code> に { joinedAt, order: 7 } を set し、meta を返す', async () => {
  state.seed['groups/JOIN01/meta'] = { name: 'テスト参加', createdAt: 1, createdBy: 'U9', schemaVersion: 2 };
  const meta = await S.joinGroup('JOIN01', 7);
  assert.deepStrictEqual(meta, { name: 'テスト参加', createdAt: 1, createdBy: 'U9', schemaVersion: 2 });
  assert.deepStrictEqual(writes(), [
    { op: 'set', path: 'users/U1/groups/JOIN01', value: { joinedAt: NOW, order: 7 } }
  ]);
});

[['order 無し', undefined], ["'3'（文字列）", '3'], ['NaN', NaN]].forEach(([label, order]) => {
  test('2 joinGroup: ' + label + ' → { joinedAt } だけ', async () => {
    state.seed['groups/JOIN01/meta'] = { name: 'テスト参加' };
    await (order === undefined ? S.joinGroup('JOIN01') : S.joinGroup('JOIN01', order));
    assert.deepStrictEqual(writes(), [
      { op: 'set', path: 'users/U1/groups/JOIN01', value: { joinedAt: NOW } }
    ]);
  });
});

// =====================================================================
// 3. setGroupOrder
// =====================================================================

test("3 setGroupOrder(['B','A','C']): users/U1/groups への update 1 回、キーは <code>/order", async () => {
  await S.setGroupOrder(['B', 'A', 'C']);
  assert.deepStrictEqual(writes(), [
    { op: 'update', path: 'users/U1/groups', value: { 'B/order': 0, 'A/order': 1, 'C/order': 2 } }
  ]);
});

test('3 setGroupOrder([]): 書き込み 0 件で resolve', async () => {
  await S.setGroupOrder([]);
  assert.strictEqual(state.writes.length, 0);
});

// =====================================================================
// 4. leaveGroup / 5. deleteGroup
// =====================================================================

test('4 leaveGroup: users/U1/groups/X1 の remove だけ（groups 側に触らない）', async () => {
  await S.leaveGroup('X1');
  assert.deepStrictEqual(writes(), [{ op: 'remove', path: 'users/U1/groups/X1', value: undefined }]);
});

test('5 deleteGroup: groups/X1 の remove → users/U1/groups/X1 の remove の順', async () => {
  await S.deleteGroup('X1');
  assert.deepStrictEqual(writes(), [
    { op: 'remove', path: 'groups/X1', value: undefined },
    { op: 'remove', path: 'users/U1/groups/X1', value: undefined }
  ]);
});

// =====================================================================
// 6. グループの中身
// =====================================================================

test('6 setGroupName: groups/G1/meta/name に名前を set', async () => {
  await S.setGroupName('G1', 'テスト新しい名前');
  assert.deepStrictEqual(writes(), [{ op: 'set', path: 'groups/G1/meta/name', value: 'テスト新しい名前' }]);
});

test('6 addMember: groups/G1/members/<mid> に { name, order } を set し、mid を返す', async () => {
  const mid = await S.addMember('G1', 'う', 2);
  assert.match(mid, /^[0-9a-z]+$/);
  assert.deepStrictEqual(writes(), [{ op: 'set', path: 'groups/G1/members/' + mid, value: { name: 'う', order: 2 } }]);
});

test('6 renameMember: groups/G1/members/m1/name に名前を set', async () => {
  await S.renameMember('G1', 'm1', 'え');
  assert.deepStrictEqual(writes(), [{ op: 'set', path: 'groups/G1/members/m1/name', value: 'え' }]);
});

test('6 removeMember: groups/G1/members/m1 の remove', async () => {
  await S.removeMember('G1', 'm1');
  assert.deepStrictEqual(writes(), [{ op: 'remove', path: 'groups/G1/members/m1', value: undefined }]);
});

// =====================================================================
// 7. addPayment
// =====================================================================

const PAY_IN = { date: '2026-09-01', memo: 'テスト宿代', payerId: 'm1', amount: 3000, participants: { m1: true, m2: true } };

test('7 addPayment: groups/G1/payments/<push key> に全キーを set し、push key を返す', async () => {
  const pid = await S.addPayment('G1', copy(PAY_IN));
  assert.strictEqual(pid, 'P1');
  assert.deepStrictEqual(writes(), [{
    op: 'set',
    path: 'groups/G1/payments/P1',
    value: {
      date: '2026-09-01', memo: 'テスト宿代', payerId: 'm1', amount: 3000,
      participants: { m1: true, m2: true },
      settlementId: null, pending: false,
      createdBy: 'U1', createdByName: 'テスト太郎',
      createdAt: NOW, updatedAt: NOW
    }
  }]);
});

test('7 addPayment: memo が無ければ空文字、pending: true なら amount は 0', async () => {
  await S.addPayment('G1', { date: '2026-09-02', payerId: 'm2', amount: 999, participants: { m2: true }, pending: true });
  const v = writes()[0].value;
  assert.strictEqual(v.memo, '');
  assert.strictEqual(v.amount, 0);
  assert.strictEqual(v.pending, true);
});

// =====================================================================
// 8. updatePayment / removePayment（清算済みのロック）
// =====================================================================

function seedPayment(pid, settlementId) {
  state.seed['groups/G1/payments/' + pid] = Object.assign(copy(PAY_IN), { settlementId: settlementId });
}

test('8 updatePayment: 清算済みなら書き込み 0 件で reject（KK_SETTLED_LOCKED）、onWriteError は 1 回', async () => {
  seedPayment('p1', 'S1');
  const calls = recordWriteErrors();
  const f = await failure(() => S.updatePayment('G1', 'p1', copy(PAY_IN)));
  assert.strictEqual(f.sync, false);
  assert.strictEqual(f.err.code, 'KK_SETTLED_LOCKED');
  assert.strictEqual(f.err.__kkReported, true);
  assert.strictEqual(state.writes.length, 0);
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].op, '支払いを更新できませんでした');
  assert.strictEqual(calls[0].err, f.err);
});

test('8 removePayment: 清算済みなら書き込み 0 件で reject（KK_SETTLED_LOCKED）、onWriteError は 1 回', async () => {
  seedPayment('p1', 'S1');
  const calls = recordWriteErrors();
  const f = await failure(() => S.removePayment('G1', 'p1'));
  assert.strictEqual(f.err.code, 'KK_SETTLED_LOCKED');
  assert.strictEqual(state.writes.length, 0);
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].op, '支払いを削除できませんでした');
});

test('8 updatePayment: 未清算なら groups/G1/payments/p1 に update（updatedBy / updatedByName / updatedAt 付き）', async () => {
  seedPayment('p1', null);
  const calls = recordWriteErrors();
  await S.updatePayment('G1', 'p1', { date: '2026-09-03', memo: 'テスト直した', payerId: 'm2', amount: 4000, participants: { m2: true } });
  assert.deepStrictEqual(writes(), [{
    op: 'update',
    path: 'groups/G1/payments/p1',
    value: {
      date: '2026-09-03', memo: 'テスト直した', payerId: 'm2', amount: 4000,
      participants: { m2: true }, pending: false,
      updatedBy: 'U1', updatedByName: 'テスト太郎', updatedAt: NOW
    }
  }]);
  assert.strictEqual(calls.length, 0);
});

test('8 removePayment: 未清算なら groups/G1/payments/p1 の remove', async () => {
  seedPayment('p1', null);
  await S.removePayment('G1', 'p1');
  assert.deepStrictEqual(writes(), [{ op: 'remove', path: 'groups/G1/payments/p1', value: undefined }]);
});

// =====================================================================
// 9. confirmSettlement
// =====================================================================

const SETTLEMENT_IN = {
  createdAt: 1790000000000,
  createdBy: 'U1',
  transfers: { t0: { from: 'm2', to: 'm1', fromName: 'い', toName: 'あ', amount: 1500, done: false } },
  paymentIds: { p1: true, p2: true }
};

test('9 confirmSettlement: groups/G1 への多パス update 1 回（settlements/<push key> と各支払いの settlementId）', async () => {
  const input = copy(SETTLEMENT_IN);
  const sid = await S.confirmSettlement('G1', input);
  assert.strictEqual(sid, 'P1');
  assert.deepStrictEqual(writes(), [{
    op: 'update',
    path: 'groups/G1',
    value: {
      'settlements/P1': {
        createdAt: 1790000000000,
        createdBy: 'U1',
        transfers: { t0: { from: 'm2', to: 'm1', fromName: 'い', toName: 'あ', amount: 1500, done: false } },
        paymentIds: { p1: true, p2: true },
        createdByName: 'テスト太郎'
      },
      'payments/p1/settlementId': 'P1',
      'payments/p2/settlementId': 'P1'
    }
  }]);
  assert.deepStrictEqual(input, SETTLEMENT_IN, '渡した清算オブジェクトを書き換えない');
});

test('9 confirmSettlement: Settle.buildSettlement の結果をそのまま書く（createdAt は端末の時刻で NOW ではない）', async () => {
  const members = [{ id: 'm1', name: 'あ' }, { id: 'm2', name: 'い' }];
  const pays = [{ id: 'p1', date: '2026-09-01', memo: 'x', payerId: 'm1', amount: 3000,
    participants: ['m1', 'm2'], settlementId: null, pending: false }];
  const built = Settle.buildSettlement(members, pays, { uid: 'U1', now: 1790000000000 });
  await S.confirmSettlement('G1', built);
  const v = writes()[0].value;
  assert.deepStrictEqual(Object.keys(v).sort(), ['payments/p1/settlementId', 'settlements/P1']);
  const rec = v['settlements/P1'];
  assert.deepStrictEqual(Object.keys(rec).sort(), ['createdAt', 'createdBy', 'createdByName', 'paymentIds', 'transfers']);
  assert.strictEqual(rec.createdAt, 1790000000000);
  assert.notStrictEqual(rec.createdAt, NOW);
  const ts = Object.keys(rec.transfers).map(k => rec.transfers[k]);
  assert.strictEqual(ts.length, 1);
  assert.deepStrictEqual(ts[0], { from: 'm2', to: 'm1', fromName: 'い', toName: 'あ', amount: 1500, done: false });
});

// =====================================================================
// 10. setTransferDone
// =====================================================================

test('10 setTransferDone(true): transfers/<tid> に done / doneAt / doneBy / doneByName を update', async () => {
  await S.setTransferDone('G1', 'S1', 't0', true);
  assert.deepStrictEqual(writes(), [{
    op: 'update',
    path: 'groups/G1/settlements/S1/transfers/t0',
    value: { done: true, doneAt: NOW, doneBy: 'U1', doneByName: 'テスト太郎' }
  }]);
});

test('10 setTransferDone(false): done: false と、doneAt / doneBy / doneByName は null（消す）で update', async () => {
  await S.setTransferDone('G1', 'S1', 't0', false);
  assert.deepStrictEqual(writes(), [{
    op: 'update',
    path: 'groups/G1/settlements/S1/transfers/t0',
    value: { done: false, doneAt: null, doneBy: null, doneByName: null }
  }]);
});

// =====================================================================
// 11. undoSettlement
// =====================================================================

test('11 undoSettlement: groups/G1 への多パス update 1 回で settlementId を null、settlements/<sid> を null', async () => {
  await S.undoSettlement('G1', 'S1', { p1: true, p2: true });
  assert.deepStrictEqual(writes(), [{
    op: 'update',
    path: 'groups/G1',
    value: { 'payments/p1/settlementId': null, 'payments/p2/settlementId': null, 'settlements/S1': null }
  }]);
});

test('11 undoSettlement: paymentIds は配列でも同じ', async () => {
  await S.undoSettlement('G1', 'S1', ['p1']);
  assert.deepStrictEqual(writes()[0].value, { 'payments/p1/settlementId': null, 'settlements/S1': null });
});

// =====================================================================
// 12. wrapWrite（失敗を 1 か所に通す）
// =====================================================================

test('12 wrapWrite: 失敗は onWriteError に（操作名, err）で 1 回、__kkReported が付き、呼び出し側にも同じ err', async () => {
  const E = new Error('テストのための失敗');
  state.fail['users/U1/groups/X1'] = E;
  const calls = recordWriteErrors();
  const f = await failure(() => S.leaveGroup('X1'));
  assert.strictEqual(f.sync, false);
  assert.strictEqual(f.err, E);
  assert.strictEqual(E.__kkReported, true);
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].op, '退出できませんでした');
  assert.strictEqual(calls[0].err, E);
});

test('12 wrapWrite: 通知済みの同じ err がもう一度通っても 2 回目は通知しない', async () => {
  const E = new Error('テストのための失敗');
  state.fail['users/U1/groups/X1'] = E;
  const calls = recordWriteErrors();
  const f1 = await failure(() => S.leaveGroup('X1'));
  const f2 = await failure(() => S.leaveGroup('X1'));
  assert.strictEqual(f1.err, E);
  assert.strictEqual(f2.err, E);
  assert.strictEqual(calls.length, 1);
});

test('12 wrapWrite: set の失敗でも同じ（setGroupName → グループ名を変更できませんでした）', async () => {
  const E = new Error('テストのための失敗');
  state.fail['groups/G1/meta/name'] = E;
  const calls = recordWriteErrors();
  const f = await failure(() => S.setGroupName('G1', 'x'));
  assert.strictEqual(f.err, E);
  assert.deepStrictEqual(calls.map(c => c.op), ['グループ名を変更できませんでした']);
});

// =====================================================================
// 13. currentUserName
// =====================================================================

test('13 currentUserName: displayName があればその名前', () => {
  assert.strictEqual(S.currentUserName(), 'テスト太郎');
});

test('13 currentUserName: displayName が空ならメールの @ より前', () => {
  FB.auth.currentUser = { uid: 'U1', displayName: '', email: 'taro@example.com' };
  assert.strictEqual(S.currentUserName(), 'taro');
});

test('13 currentUserName: displayName もメールも空なら（名前なし）', () => {
  FB.auth.currentUser = { uid: 'U1', displayName: '', email: '' };
  assert.strictEqual(S.currentUserName(), '（名前なし）');
});

test('13 currentUserName は書き込む名前にも使われる（displayName 空 → メールの @ より前で createdByName）', async () => {
  FB.auth.currentUser = { uid: 'U1', displayName: '', email: 'taro@example.com' };
  await S.addPayment('G1', copy(PAY_IN));
  assert.strictEqual(writes()[0].value.createdByName, 'taro');
});

// =====================================================================
// 14. ログインしていない・初期化できていない
// =====================================================================

test('14 ログインしていない: leaveGroup は（同期で）ログインしていませんで失敗し、書き込み 0 件', async () => {
  FB.auth.currentUser = null;
  const f = await failure(() => S.leaveGroup('X1'));
  assert.strictEqual(f.sync, true);
  assert.strictEqual(f.err.message, 'ログインしていません');
  assert.strictEqual(state.writes.length, 0);
});

test('14 ready: false: uid を使わない setGroupName は（同期で）Firebase が初期化できていませんで失敗', async () => {
  FB.ready = false;
  const f = await failure(() => S.setGroupName('G1', 'x'));
  assert.strictEqual(f.sync, true);
  assert.strictEqual(f.err.message, 'Firebase が初期化できていません');
  assert.strictEqual(state.writes.length, 0);
});

test('14 ready: false: uid を先に使う leaveGroup は、ログインしていませんで失敗する（現状）', async () => {
  FB.ready = false;
  const f = await failure(() => S.leaveGroup('X1'));
  assert.strictEqual(f.sync, true);
  assert.strictEqual(f.err.message, 'ログインしていません');
  assert.strictEqual(state.writes.length, 0);
});

// =====================================================================
// 参考: 監視の張り方（書き込みではないが、パスを固定しておく）
// =====================================================================

test('参考 watchMyGroups: users/U1/groups に value 監視を 1 本、呼び直すと前のを外す', () => {
  S.watchMyGroups(() => {});
  S.watchMyGroups(() => {});
  assert.deepStrictEqual(state.listens.map(l => [l.op, l.path, l.event]), [
    ['on', 'users/U1/groups', 'value'],
    ['off', 'users/U1/groups', 'value'],
    ['on', 'users/U1/groups', 'value']
  ]);
  S.stopWatchMyGroups();
});

// =====================================================================

(async () => {
  let passed = 0;
  const failures = [];
  for (const t of tests) {
    reset();
    try {
      await t.fn();
      passed++;
      console.log('  ok   ' + t.name);
    } catch (e) {
      failures.push(t.name);
      console.log('  FAIL ' + t.name + '\n       ' + String(e && e.message || e).split('\n').join('\n       '));
    }
  }
  console.log('');
  if (failures.length === 0) {
    console.log('すべて通過: ' + passed + ' 件');
    process.exit(0);
  } else {
    console.log('失敗 ' + failures.length + ' 件 / 通過 ' + passed + ' 件');
    process.exit(1);
  }
})();
