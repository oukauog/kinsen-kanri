/*
 * tests/calc.test.js — js/calc.js の挙動固定テスト
 * 実行: node tests/calc.test.js
 *
 * 期待値の出所は docs/30_テストケース_清算.md（v1 の実挙動）。
 * v2 でロジックを変えたくなったら、まずここの期待値を相談役と合意してから直すこと。
 */
'use strict';

const assert = require('assert');
const Calc = require('../js/calc.js');

let passed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log('  ok   ' + name);
  } catch (e) {
    failures.push({ name, e });
    console.log('  FAIL ' + name + '\n       ' + e.message.split('\n').join('\n       '));
  }
}

function near(actual, expected, msg, tol) {
  const t = tol == null ? 0.005 : tol;
  assert.ok(Math.abs(actual - expected) <= t,
    (msg || '') + ' 期待 ' + expected + ' / 実際 ' + actual);
}

// =====================================================================
// ケース1: 4人・36件（実データ由来）
// =====================================================================

const MEMBERS1 = [
  { id: 'A', name: 'A' },
  { id: 'B', name: 'B' },
  { id: 'C', name: 'C' },
  { id: 'D', name: 'D' }
];

const ALL = ['A', 'B', 'C', 'D'];
// [支払った人, 金額, 割り勘対象]
const RAW1 = [
  ['A', 8460, ALL],
  ['C', 800, ALL],
  ['A', 900, ALL],
  ['C', 6400, ALL],
  ['A', 419, ['A', 'C']],
  ['C', 10100, ['A', 'C']],
  ['C', 7200, ALL],
  ['C', 5600, ALL],
  ['C', 1240, ALL],
  ['C', 400, ALL],
  ['A', 430, ALL],
  ['A', 1000, ALL],
  ['D', 9150, ALL],
  ['A', 2000, ALL],
  ['A', 1400, ALL],
  ['A', 4000, ALL],
  ['A', 1200, ALL],
  ['C', 4708, ALL],
  ['A', 210, ALL],
  ['A', 730, ALL],
  ['A', 300, ALL],
  ['C', 15200, ['A', 'C']],
  ['A', 3500, ALL],
  ['A', 5401, ALL],
  ['A', 300, ALL],
  ['A', 1200, ALL],
  ['A', 300, ALL],
  ['C', 1290, ['A', 'C']],
  ['C', 28369, ['A', 'C', 'D']],
  ['C', 2980, ALL],
  ['A', 2980, ALL],
  ['C', 620, ALL],
  ['D', 370, ALL],
  ['D', 1920, ALL],
  ['D', 7450, ALL],
  ['A', 58740, ALL]
];

const PAYMENTS1 = RAW1.map((r, i) => ({
  id: 'p' + (i + 1),
  date: '2026-09-01',
  memo: '',
  payerId: r[0],
  amount: r[1],
  participants: r[2].slice(),
  settlementId: null,
  pending: false
}));

console.log('ケース1: 4人・36件');

test('件数が 36 件', () => {
  assert.strictEqual(PAYMENTS1.length, 36);
});

test('残高（丸めなし）が仕様書の表と一致する', () => {
  const bal = Calc.calcBalances(MEMBERS1, PAYMENTS1);
  near(bal.A, 35036.92, 'A の残高');
  near(bal.B, -35472.25, 'B の残高');
  near(bal.C, 26473.92, 'C の残高');
  near(bal.D, -26038.58, 'D の残高');
});

test('払った合計・負担分が仕様書の表と一致する', () => {
  const paid = { A: 0, B: 0, C: 0, D: 0 };
  PAYMENTS1.forEach(p => { paid[p.payerId] += p.amount; });
  assert.strictEqual(paid.A, 93470, 'A の払った合計');
  assert.strictEqual(paid.B, 0, 'B の払った合計');
  assert.strictEqual(paid.C, 84907, 'C の払った合計');
  assert.strictEqual(paid.D, 18890, 'D の払った合計');

  const bal = Calc.calcBalances(MEMBERS1, PAYMENTS1);
  near(paid.A - bal.A, 58433.08, 'A の負担分');
  near(paid.B - bal.B, 35472.25, 'B の負担分');
  near(paid.C - bal.C, 58433.08, 'C の負担分');
  near(paid.D - bal.D, 44928.58, 'D の負担分');
});

test('支払い総額が 197267 円', () => {
  const total = PAYMENTS1.reduce((s, p) => s + p.amount, 0);
  assert.strictEqual(total, 197267);
});

test('残高の合計が 0（誤差 1e-6 以下）', () => {
  const bal = Calc.calcBalances(MEMBERS1, PAYMENTS1);
  const sum = Object.keys(bal).reduce((s, k) => s + bal[k], 0);
  assert.ok(Math.abs(sum) <= 1e-6, '残高合計 ' + sum);
});

test('清算は 3 本、金額も順序も仕様書どおり', () => {
  const txns = Calc.calcSettlement(MEMBERS1, PAYMENTS1);
  assert.strictEqual(txns.length, 3, '送金の本数');
  assert.deepStrictEqual(
    txns.map(t => [t.from, t.to, t.amount]),
    [['B', 'A', 35037], ['B', 'C', 435], ['D', 'C', 26039]]
  );
});

test('members / payments を ID キーのオブジェクトで渡しても同じ結果（v2 のデータ形）', () => {
  const membersObj = {
    A: { name: 'A', order: 0 },
    B: { name: 'B', order: 1 },
    C: { name: 'C', order: 2 },
    D: { name: 'D', order: 3 }
  };
  const paymentsObj = {};
  PAYMENTS1.forEach(p => {
    const parts = {};
    p.participants.forEach(mid => { parts[mid] = true; });
    paymentsObj[p.id] = Object.assign({}, p, { participants: parts, id: undefined });
  });
  const txns = Calc.calcSettlement(membersObj, paymentsObj);
  assert.deepStrictEqual(
    txns.map(t => [t.from, t.to, t.amount]),
    [['B', 'A', 35037], ['B', 'C', 435], ['D', 'C', 26039]]
  );
  const bal = Calc.calcBalances(membersObj, paymentsObj);
  near(bal.A, 35036.92, 'A の残高（オブジェクト形）');
});

// =====================================================================
// ケース2: 端数と境界
// =====================================================================

console.log('ケース2: 端数と境界');

test('2 人で 1 円 → 残高 +0.5 / -0.5、清算は 0 本（閾値 0.5 の挙動）', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }];
  const pays = [{ payerId: 'a', amount: 1, participants: ['a', 'b'] }];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 0.5, 'a の残高');
  near(bal.b, -0.5, 'b の残高');
  assert.strictEqual(Calc.calcSettlement(members, pays).length, 0, '送金の本数');
});

test('3 人で 100 円 → +66.67 / -33.33 / -33.33、清算は 2 本で各 33 円', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }, { id: 'c', name: 'う' }];
  const pays = [{ payerId: 'a', amount: 100, participants: ['a', 'b', 'c'] }];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 66.67, 'a の残高');
  near(bal.b, -33.33, 'b の残高');
  near(bal.c, -33.33, 'c の残高');
  const txns = Calc.calcSettlement(members, pays);
  assert.strictEqual(txns.length, 2, '送金の本数');
  assert.deepStrictEqual(txns.map(t => [t.from, t.to, t.amount]),
    [['い', 'あ', 33], ['う', 'あ', 33]]);
});

test('支払者が割り勘対象に含まれない → 支払者に加算しない（v1 の癖。残高合計が 0 にならない）', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }, { id: 'c', name: 'う' }];
  const pays = [{ payerId: 'a', amount: 300, participants: ['b', 'c'] }];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 0, 'a（支払者）の残高');
  near(bal.b, -150, 'b の残高');
  near(bal.c, -150, 'c の残高');
  const sum = bal.a + bal.b + bal.c;
  near(sum, -300, '残高の合計（0 にならないのが v1 の挙動）');
  // 貸し手がいないので送金は作られない
  assert.strictEqual(Calc.calcSettlement(members, pays).length, 0, '送金の本数');
});

test('割り勘対象 0 人の支払いは無視する', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }];
  const pays = [
    { payerId: 'a', amount: 1000, participants: [] },
    { payerId: 'a', amount: 200, participants: ['a', 'b'] }
  ];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 100, 'a の残高');
  near(bal.b, -100, 'b の残高');
});

test('支払いが 0 件 → 全員 0、清算 0 本', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }];
  const bal = Calc.calcBalances(members, []);
  assert.deepStrictEqual(bal, { a: 0, b: 0 });
  assert.strictEqual(Calc.calcSettlement(members, []).length, 0);
});

test('メンバー一覧にいない人が対象に混ざっても計算できる（v1 と同じく動的に追加）', () => {
  const members = [{ id: 'a', name: 'あ' }];
  const pays = [{ payerId: 'a', amount: 200, participants: ['a', 'x'] }];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 100, 'a の残高');
  near(bal.x, -100, 'x の残高');
  // ただし送金リストは members にいる人しか作らない（v1 と同じ）
  assert.strictEqual(Calc.calcSettlement(members, pays).length, 0, '送金の本数');
});

test('participants が {mid:false} のキーは対象外として扱う', () => {
  const members = [{ id: 'a', name: 'あ' }, { id: 'b', name: 'い' }];
  const pays = [{ payerId: 'a', amount: 100, participants: { a: true, b: false } }];
  const bal = Calc.calcBalances(members, pays);
  near(bal.a, 0, 'a の残高');
  near(bal.b, 0, 'b の残高');
});

// =====================================================================
// 小道具
// =====================================================================

console.log('表示用の小道具');

test('share(): 1 人あたりの負担額（丸めない）', () => {
  near(Calc.share(100, 3), 33.3333, '', 0.0001);
  assert.strictEqual(Calc.share(100, 0), 0, '0 人なら 0');
});

test('money(): 絶対値を四捨五入して 3 桁区切り（v1 と同じ）', () => {
  assert.strictEqual(Calc.money(35036.92), '¥35,037');
  assert.strictEqual(Calc.money(-1200), '¥1,200');
  assert.strictEqual(Calc.money(0), '¥0');
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
