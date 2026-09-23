/*
 * tests/settle.test.js — 清算のイベント化まわりの固定テスト
 * 実行: node tests/settle.test.js（まとめては node tests/run_all.js）
 *
 * ここが通る = 「清算してから追加した分だけが次の清算に乗る」
 * 「金額確認中は計算に入らない」「取り消せるのは最新だけ」が守られている。
 */
'use strict';

const assert = require('assert');
const Settle = require('../js/settle.js');
const Calc = require('../js/calc.js');

let passed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log('  ok   ' + name);
  } catch (e) {
    failures.push(name);
    console.log('  FAIL ' + name + '\n       ' + e.message.split('\n').join('\n       '));
  }
}

const UID = 'uid-test';
const NOW = 1800000000000;

const M3 = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }, { id: 'c', name: 'う' }];

function pay(id, payerId, amount, participants, extra) {
  return Object.assign({
    id: id, date: '2026-09-01', memo: id, payerId: payerId, amount: amount,
    participants: participants.slice(), settlementId: null, pending: false
  }, extra || {});
}

// =====================================================================
console.log('① 計算対象の選び方');

test('未清算かつ確認中でない支払いだけが対象になる', () => {
  const pays = [
    pay('p1', 'a', 3000, ['a', 'b', 'c']),
    pay('p2', 'b', 1500, ['a', 'b'], { settlementId: 's1' }),     // 清算済み
    pay('p3', 'c', 0, ['a', 'b', 'c'], { pending: true }),        // 金額確認中
    pay('p4', 'a', 600, ['a', 'c'])
  ];
  assert.deepStrictEqual(Settle.pickUnsettled(pays).map(p => p.id), ['p1', 'p4']);
  assert.deepStrictEqual(Settle.pickPending(pays).map(p => p.id), ['p3']);
  assert.deepStrictEqual(Settle.pickSettled(pays).map(p => p.id), ['p2']);
  assert.deepStrictEqual(Settle.pickAllButPending(pays).map(p => p.id), ['p1', 'p2', 'p4']);
});

test('settlementId が undefined / 無い場合も未清算として扱う', () => {
  const pays = [
    { id: 'p1', payerId: 'a', amount: 100, participants: ['a', 'b'] },
    { id: 'p2', payerId: 'a', amount: 100, participants: ['a', 'b'], settlementId: undefined }
  ];
  assert.deepStrictEqual(Settle.pickUnsettled(pays).map(p => p.id), ['p1', 'p2']);
});

test('pending が false / 無い場合は対象に入る', () => {
  const pays = [
    { id: 'p1', payerId: 'a', amount: 100, participants: ['a', 'b'], pending: false },
    { id: 'p2', payerId: 'a', amount: 100, participants: ['a', 'b'] }
  ];
  assert.strictEqual(Settle.pickUnsettled(pays).length, 2);
});

test('{pid:{...}} のオブジェクト形でも同じ結果（Firebase の形）', () => {
  const pays = {
    p1: { payerId: 'a', amount: 3000, participants: { a: true, b: true, c: true }, settlementId: null, pending: false },
    p2: { payerId: 'b', amount: 1500, participants: { a: true, b: true }, settlementId: 's1', pending: false },
    p3: { payerId: 'c', amount: 0, participants: { a: true }, settlementId: null, pending: true }
  };
  assert.deepStrictEqual(Settle.pickUnsettled(pays).map(p => p.id).sort(), ['p1']);
  assert.deepStrictEqual(Settle.pickPending(pays).map(p => p.id), ['p3']);
});

test('金額確認中を外すので残高が変わる（確認中は 0 円扱いですらない）', () => {
  const pays = [
    pay('p1', 'a', 3000, ['a', 'b', 'c']),
    pay('p2', 'b', 99999, ['a', 'b', 'c'], { pending: true })
  ];
  const bal = Calc.calcBalances(M3, Settle.pickUnsettled(pays));
  assert.strictEqual(Math.round(bal.a), 2000);
  assert.strictEqual(Math.round(bal.b), -1000);
  assert.strictEqual(Math.round(bal.c), -1000);
});

// =====================================================================
console.log('② 確定ペイロードの形');

test('transfers / paymentIds / createdAt / createdBy が仕様どおり', () => {
  const pays = [pay('p1', 'a', 3000, ['a', 'b', 'c'])];
  const s = Settle.buildSettlement(M3, pays, { uid: UID, now: NOW });
  assert.strictEqual(s.createdAt, NOW);
  assert.strictEqual(s.createdBy, UID);
  assert.deepStrictEqual(s.paymentIds, { p1: true });
  const tids = Object.keys(s.transfers);
  assert.strictEqual(tids.length, 2, '送金は 2 本');
  const t = s.transfers[tids[0]];
  assert.deepStrictEqual(Object.keys(t).sort(),
    ['amount', 'done', 'from', 'fromName', 'to', 'toName']);
  assert.strictEqual(t.done, false);
  assert.strictEqual(t.amount, 1000);
});

test('transfers の from / to はメンバー ID、fromName / toName は名前', () => {
  const pays = [pay('p1', 'a', 3000, ['a', 'b', 'c'])];
  const s = Settle.buildSettlement(M3, pays, { uid: UID, now: NOW });
  Settle.transferList(s).forEach(t => {
    assert.ok(['a', 'b', 'c'].indexOf(t.from) >= 0, 'from が ID でない: ' + t.from);
    assert.ok(['a', 'b', 'c'].indexOf(t.to) >= 0, 'to が ID でない: ' + t.to);
    assert.strictEqual(t.toName, 'あ');
  });
});

test('送金の ID は順番が崩れない形（t001, t002, …）', () => {
  assert.strictEqual(Settle.transferId(0), 't001');
  assert.strictEqual(Settle.transferId(9), 't010');
  assert.strictEqual(Settle.transferId(99), 't100');
  const pays = [pay('p1', 'a', 3000, ['a', 'b', 'c'])];
  const s = Settle.buildSettlement(M3, pays, { uid: UID, now: NOW });
  assert.deepStrictEqual(Object.keys(s.transfers).sort(), ['t001', 't002']);
});

test('paymentIds に清算済み・確認中は入らない', () => {
  const pays = [
    pay('p1', 'a', 3000, ['a', 'b', 'c']),
    pay('p2', 'b', 1500, ['a', 'b'], { settlementId: 's-old' }),
    pay('p3', 'c', 0, ['a', 'b'], { pending: true })
  ];
  const s = Settle.buildSettlement(M3, pays, { uid: UID, now: NOW });
  assert.deepStrictEqual(s.paymentIds, { p1: true });
});

test('送金額の合計が、借りている人の合計と一致する', () => {
  const pays = [pay('p1', 'a', 3000, ['a', 'b', 'c']), pay('p2', 'b', 600, ['a', 'b', 'c'])];
  const s = Settle.buildSettlement(M3, pays, { uid: UID, now: NOW });
  const sum = Settle.transferList(s).reduce((x, t) => x + t.amount, 0);
  const bal = Calc.calcBalances(M3, Settle.pickUnsettled(pays));
  const debt = Object.keys(bal).reduce((x, k) => x + (bal[k] < 0 ? -bal[k] : 0), 0);
  assert.ok(Math.abs(sum - debt) <= 1, '送金合計 ' + sum + ' / 借り合計 ' + debt);
});

// =====================================================================
console.log('③ 確定できない場合');

test('未清算の支払いが 0 件なら null', () => {
  assert.strictEqual(Settle.buildSettlement(M3, [], { uid: UID, now: NOW }), null);
  const allSettled = [pay('p1', 'a', 3000, ['a', 'b', 'c'], { settlementId: 's1' })];
  assert.strictEqual(Settle.buildSettlement(M3, allSettled, { uid: UID, now: NOW }), null);
});

test('確認中しか無ければ null', () => {
  const pays = [pay('p1', 'a', 0, ['a', 'b', 'c'], { pending: true })];
  assert.strictEqual(Settle.buildSettlement(M3, pays, { uid: UID, now: NOW }), null);
});

test('貸し借りが無ければ（送金 0 本）null', () => {
  const pays = [pay('p1', 'a', 300, ['a', 'b', 'c']), pay('p2', 'b', 300, ['a', 'b', 'c']),
    pay('p3', 'c', 300, ['a', 'b', 'c'])];
  assert.strictEqual(Settle.buildSettlement(M3, pays, { uid: UID, now: NOW }), null);
});

test('閾値 0.5 以下の差しかないときも null（v1 の清算と同じ判定）', () => {
  const M2 = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }];
  const pays = [pay('p1', 'a', 1, ['a', 'b'])];
  assert.strictEqual(Settle.buildSettlement(M2, pays, { uid: UID, now: NOW }), null);
});

// =====================================================================
console.log('④ 最新判定と取り消し可否');

const SETTLEMENTS = {
  s1: { createdAt: 1000, createdBy: UID, transfers: { t001: { from: 'b', to: 'a', amount: 100, done: false } }, paymentIds: { p1: true } },
  s2: { createdAt: 3000, createdBy: UID, transfers: { t001: { from: 'c', to: 'a', amount: 200, done: true } }, paymentIds: { p2: true, p3: true } },
  s3: { createdAt: 2000, createdBy: UID, transfers: {}, paymentIds: {} }
};

test('listSettlements は新しい順', () => {
  assert.deepStrictEqual(Settle.listSettlements(SETTLEMENTS).map(s => s.id), ['s2', 's3', 's1']);
});

test('latestSettlement は createdAt 最大の 1 件', () => {
  assert.strictEqual(Settle.latestSettlement(SETTLEMENTS).id, 's2');
  assert.strictEqual(Settle.latestSettlement({}), null);
  assert.strictEqual(Settle.latestSettlement(null), null);
});

test('取り消せるのは最新の 1 件だけ', () => {
  assert.strictEqual(Settle.canUndo(SETTLEMENTS, 's2'), true);
  assert.strictEqual(Settle.canUndo(SETTLEMENTS, 's3'), false);
  assert.strictEqual(Settle.canUndo(SETTLEMENTS, 's1'), false);
  assert.strictEqual(Settle.canUndo({}, 's1'), false);
});

test('送金チェックの有無を判定する', () => {
  assert.strictEqual(Settle.hasAnyDone(SETTLEMENTS.s1), false);
  assert.strictEqual(Settle.hasAnyDone(SETTLEMENTS.s2), true);
  assert.strictEqual(Settle.hasAnyDone(SETTLEMENTS.s3), false);
  assert.strictEqual(Settle.hasAnyDone(null), false);
});

test('全部チェック済みなら完了（送金 0 本は完了にしない）', () => {
  assert.strictEqual(Settle.allDone(SETTLEMENTS.s1), false);
  assert.strictEqual(Settle.allDone(SETTLEMENTS.s2), true);
  assert.strictEqual(Settle.allDone(SETTLEMENTS.s3), false);
  const mixed = { transfers: { t001: { done: true }, t002: { done: false } } };
  assert.strictEqual(Settle.allDone(mixed), false);
});

test('対象件数を数えられる', () => {
  assert.strictEqual(Settle.targetCount(SETTLEMENTS.s2), 2);
  assert.strictEqual(Settle.targetCount(SETTLEMENTS.s3), 0);
  assert.strictEqual(Settle.targetCount(null), 0);
});

// =====================================================================
console.log('⑤ 清算 → 追加 → 再清算（追加分だけが乗る）');

// docs/30_テストケース_清算.md ケース1 の 36 件
const MEMBERS1 = [
  { id: 'A', name: 'A' }, { id: 'B', name: 'B' }, { id: 'C', name: 'C' }, { id: 'D', name: 'D' }
];
const ALL = ['A', 'B', 'C', 'D'];
const RAW1 = [
  ['A', 8460, ALL], ['C', 800, ALL], ['A', 900, ALL], ['C', 6400, ALL],
  ['A', 419, ['A', 'C']], ['C', 10100, ['A', 'C']], ['C', 7200, ALL], ['C', 5600, ALL],
  ['C', 1240, ALL], ['C', 400, ALL], ['A', 430, ALL], ['A', 1000, ALL],
  ['D', 9150, ALL], ['A', 2000, ALL], ['A', 1400, ALL], ['A', 4000, ALL],
  ['A', 1200, ALL], ['C', 4708, ALL], ['A', 210, ALL], ['A', 730, ALL],
  ['A', 300, ALL], ['C', 15200, ['A', 'C']], ['A', 3500, ALL], ['A', 5401, ALL],
  ['A', 300, ALL], ['A', 1200, ALL], ['A', 300, ALL], ['C', 1290, ['A', 'C']],
  ['C', 28369, ['A', 'C', 'D']], ['C', 2980, ALL], ['A', 2980, ALL], ['C', 620, ALL],
  ['D', 370, ALL], ['D', 1920, ALL], ['D', 7450, ALL], ['A', 58740, ALL]
];
const CASE1 = RAW1.map((r, i) => pay('c' + (i + 1), r[0], r[1], r[2]));

test('1 回目の清算はケース1 の期待値（B→A 35037 / B→C 435 / D→C 26039）', () => {
  const s = Settle.buildSettlement(MEMBERS1, CASE1, { uid: UID, now: NOW });
  assert.deepStrictEqual(
    Settle.transferList(s).map(t => [t.fromName, t.toName, t.amount]),
    [['B', 'A', 35037], ['B', 'C', 435], ['D', 'C', 26039]]);
  assert.strictEqual(Object.keys(s.paymentIds).length, 36);
});

test('清算後に 3 件足すと、2 回目は足した 3 件だけで計算される', () => {
  // 1 回目を確定したつもりで settlementId を入れる（store の多パス update と同じ結果）
  const s1 = Settle.buildSettlement(MEMBERS1, CASE1, { uid: UID, now: NOW });
  const after = CASE1.map(p => Object.assign({}, p,
    Object.prototype.hasOwnProperty.call(s1.paymentIds, p.id) ? { settlementId: 'sid-1' } : {}));

  // 追加の 3 件
  after.push(pay('n1', 'B', 3000, ALL));
  after.push(pay('n2', 'B', 1000, ['B', 'D']));
  after.push(pay('n3', 'A', 0, ALL, { pending: true }));   // 確認中は乗らない

  const target = Settle.pickUnsettled(after);
  assert.deepStrictEqual(target.map(p => p.id), ['n1', 'n2'], '対象は追加の 2 件だけ');

  const s2 = Settle.buildSettlement(MEMBERS1, after, { uid: UID, now: NOW + 1000 });
  assert.deepStrictEqual(Object.keys(s2.paymentIds).sort(), ['n1', 'n2']);

  // 期待値: n1 = B が 3000 を 4 人で → B +2250 / 他 -750、n2 = B が 1000 を B,D で → B +500 / D -500
  // 残高: A -750, B +2750, C -750, D -1250 → 送金 3 本
  assert.deepStrictEqual(
    Settle.transferList(s2).map(t => [t.fromName, t.toName, t.amount]),
    [['D', 'B', 1250], ['A', 'B', 750], ['C', 'B', 750]]);
});

test('2 回目の清算に 1 回目の支払いが混ざらない', () => {
  const s1 = Settle.buildSettlement(MEMBERS1, CASE1, { uid: UID, now: NOW });
  const after = CASE1.map(p => Object.assign({}, p, { settlementId: 'sid-1' }));
  after.push(pay('n1', 'B', 3000, ALL));
  const s2 = Settle.buildSettlement(MEMBERS1, after, { uid: UID, now: NOW + 1000 });
  Object.keys(s1.paymentIds).forEach(pid => {
    assert.ok(!Object.prototype.hasOwnProperty.call(s2.paymentIds, pid),
      '1 回目の ' + pid + ' が 2 回目にも入っている');
  });
});

test('取り消すと（settlementId を null に戻すと）元の対象に戻る', () => {
  const s1 = Settle.buildSettlement(MEMBERS1, CASE1, { uid: UID, now: NOW });
  const settled = CASE1.map(p => Object.assign({}, p, { settlementId: 'sid-1' }));
  assert.strictEqual(Settle.pickUnsettled(settled).length, 0);
  const undone = settled.map(p => Object.assign({}, p, { settlementId: null }));
  const s3 = Settle.buildSettlement(MEMBERS1, undone, { uid: UID, now: NOW + 2000 });
  assert.deepStrictEqual(
    Settle.transferList(s3).map(t => [t.fromName, t.toName, t.amount]),
    Settle.transferList(s1).map(t => [t.fromName, t.toName, t.amount]));
});

test('累計（pickAllButPending）は清算済みも含めて計算する', () => {
  const settled = CASE1.map(p => Object.assign({}, p, { settlementId: 'sid-1' }));
  settled.push(pay('n1', 'B', 3000, ALL));
  const balUnsettled = Calc.calcBalances(MEMBERS1, Settle.pickUnsettled(settled));
  const balAll = Calc.calcBalances(MEMBERS1, Settle.pickAllButPending(settled));
  assert.strictEqual(Math.round(balUnsettled.B), 2250, '未清算のみ');
  assert.ok(Math.abs(balAll.B - (-35472.25 + 2250)) < 0.01, '累計 ' + balAll.B);
});

// =====================================================================
console.log('');
if (failures.length === 0) {
  console.log('すべて通過: ' + passed + ' 件');
  process.exit(0);
} else {
  console.log('失敗 ' + failures.length + ' 件 / 通過 ' + passed + ' 件');
  process.exit(1);
}
