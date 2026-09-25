/*
 * tests/group_order.test.js — サイドバーのグループの並び順（工事5）の固定テスト
 * 実行: node tests/group_order.test.js（まとめては node tests/run_all.js）
 *
 * ここが通る = 「order があれば order 順、無ければ joinedAt 順、同点はコード順」
 * 「新しく入れるグループは一番下（最大 + 1、空なら 0）」が守られている。
 */
'use strict';

const assert = require('assert');
const GO = require('../js/group_order.js');

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

// joinedAt は Firebase のサーバ時刻（ミリ秒）
const T = 1790000000000;

// =====================================================================
console.log('sortCodes');

test('(1) 全部 order あり → order の小さい順', () => {
  const g = {
    AAA111: { joinedAt: T + 1, order: 2 },
    BBB222: { joinedAt: T + 2, order: 0 },
    CCC333: { joinedAt: T + 3, order: 1 }
  };
  assert.deepStrictEqual(GO.sortCodes(g), ['BBB222', 'CCC333', 'AAA111']);
});

test('(2) 全部 order なし → joinedAt の古い順', () => {
  const g = {
    AAA111: { joinedAt: T + 300 },
    BBB222: { joinedAt: T + 100 },
    CCC333: { joinedAt: T + 200 }
  };
  assert.deepStrictEqual(GO.sortCodes(g), ['BBB222', 'CCC333', 'AAA111']);
});

test('(3) 混在 → キー（order か joinedAt）で比べる。joinedAt の方は通常は後ろ', () => {
  const g = {
    OLD001: { joinedAt: T + 100 },            // キー = T+100
    NEW002: { joinedAt: T + 999, order: 5 },  // キー = 5
    NEW003: { joinedAt: T + 50, order: 0 },   // キー = 0
    OLD004: { joinedAt: T + 10 }              // キー = T+10
  };
  assert.deepStrictEqual(GO.sortCodes(g), ['NEW003', 'NEW002', 'OLD004', 'OLD001']);
});

test('(3) 混在: order が joinedAt より大きければ order の方が後ろ', () => {
  const g = {
    OLD001: { joinedAt: T },
    NEW002: { joinedAt: T - 5, order: T + 1 }   // nextOrder で入った想定
  };
  assert.deepStrictEqual(GO.sortCodes(g), ['OLD001', 'NEW002']);
});

test('(4) 同点はコードの文字列順', () => {
  const g = {
    ZZZ999: { joinedAt: T, order: 1 },
    AAA111: { joinedAt: T + 5, order: 1 },
    MMM555: { joinedAt: T + 9, order: 1 }
  };
  assert.deepStrictEqual(GO.sortCodes(g), ['AAA111', 'MMM555', 'ZZZ999']);
});

test('(4) 同点はコード順（order も joinedAt も無い → キー 0 同士）', () => {
  const g = { BBB222: {}, AAA111: {}, CCC333: {} };
  assert.deepStrictEqual(GO.sortCodes(g), ['AAA111', 'BBB222', 'CCC333']);
});

test('(4) コード順は文字列の順（大文字・数字の並び。localeCompare ではない）', () => {
  const g = { B00001: { order: 0 }, A00009: { order: 0 }, '900000': { order: 0 } };
  assert.deepStrictEqual(GO.sortCodes(g), ['900000', 'A00009', 'B00001']);
});

test('(6) order が文字列や null なら無いものとして joinedAt で並べる', () => {
  const g = {
    STR001: { joinedAt: T + 3, order: '0' },
    NUL002: { joinedAt: T + 1, order: null },
    NUM003: { joinedAt: T + 2, order: 0 }
  };
  // NUM003 はキー 0、NUL002 は T+1、STR001 は T+3
  assert.deepStrictEqual(GO.sortCodes(g), ['NUM003', 'NUL002', 'STR001']);
});

test('(6) joinedAt も数値でなければキー 0', () => {
  assert.strictEqual(GO.sortKey({ joinedAt: 'x', order: undefined }), 0);
  assert.strictEqual(GO.sortKey(null), 0);
  assert.strictEqual(GO.sortKey(true), 0);
  assert.strictEqual(GO.sortKey({ order: NaN, joinedAt: T }), T);
});

test('空・null の一覧は空配列', () => {
  assert.deepStrictEqual(GO.sortCodes({}), []);
  assert.deepStrictEqual(GO.sortCodes(null), []);
  assert.deepStrictEqual(GO.sortCodes(undefined), []);
});

test('引数のオブジェクトを書き換えない', () => {
  const g = { B: { order: 1 }, A: { order: 0 } };
  const before = JSON.stringify(g);
  GO.sortCodes(g);
  assert.strictEqual(JSON.stringify(g), before);
});

// =====================================================================
console.log('nextOrder');

test('(5) 一覧が空なら 0', () => {
  assert.strictEqual(GO.nextOrder({}), 0);
  assert.strictEqual(GO.nextOrder(null), 0);
});

test('(5) 全部 order あり → 最大 + 1', () => {
  assert.strictEqual(GO.nextOrder({ A: { order: 0 }, B: { order: 3 }, C: { order: 1 } }), 4);
});

test('(5) order なしが混ざると joinedAt が最大 → joinedAt + 1（一番下に入る）', () => {
  const g = { A: { order: 0 }, B: { joinedAt: T + 7 } };
  assert.strictEqual(GO.nextOrder(g), T + 8);
});

test('(6) order が文字列や null のときは joinedAt で最大を取る', () => {
  const g = { A: { joinedAt: T, order: '99999999999999' }, B: { joinedAt: T - 1, order: null } };
  assert.strictEqual(GO.nextOrder(g), T + 1);
});

test('(5) nextOrder で入れたグループは sortCodes で必ず一番下', () => {
  const g = {
    OLD1: { joinedAt: T + 50 },
    OLD2: { joinedAt: T + 10 },
    DND1: { joinedAt: T + 1, order: 0 }
  };
  g.NEW9 = { joinedAt: T + 60, order: GO.nextOrder(g) };
  const codes = GO.sortCodes(g);
  assert.strictEqual(codes[codes.length - 1], 'NEW9');
});

test('(5) ドロップ後（0..n-1）に nextOrder で入れると n になり一番下', () => {
  const g = { B: { joinedAt: T, order: 0 }, A: { joinedAt: T + 1, order: 1 }, C: { joinedAt: T + 2, order: 2 } };
  assert.strictEqual(GO.nextOrder(g), 3);
  g.D = { joinedAt: T + 3, order: 3 };
  assert.deepStrictEqual(GO.sortCodes(g), ['B', 'A', 'C', 'D']);
});

test('(5) キー 0 だけの一覧（order も joinedAt も無い）なら 1', () => {
  assert.strictEqual(GO.nextOrder({ A: {} }), 1);
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
