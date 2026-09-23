/*
 * tests/migrate.test.js — 旧ルーム → v2 の変換の固定テスト
 * 実行: node tests/migrate.test.js（まとめては node tests/run_all.js）
 *
 * ここが通る = 友人の実データ（rooms/Y39EN6）を変換しても
 * 金額・割り勘対象・削除済みの扱いが変わらない、という担保。
 * 期待値を変えるときは相談役と合意してから。
 */
'use strict';

const assert = require('assert');
const Migrate = require('../js/migrate.js');
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

const UID = 'uid-hanai';
const NOW = 1700000000000;

// ---------------------------------------------------------------- ケース①
console.log('ケース①: 1 グループ・数件');

const ROOM1 = {
  groups: [
    {
      id: 'g1', name: 'テスト旅行',
      members: [{ id: 'm1', name: 'あ' }, { id: 'm2', name: 'い' }, { id: 'm3', name: 'う' }]
    }
  ],
  payments: [
    { id: 'p1', groupId: 'g1', date: '2026-08-01', memo: '宿', payerId: 'm1', amount: 30000, participants: ['m1', 'm2', 'm3'] },
    { id: 'p2', groupId: 'g1', date: '2026-08-02', memo: '昼食', payerId: 'm2', amount: 4500, participants: ['m1', 'm2'] }
  ],
  updatedAt: 1699999999999
};

test('コードを引き継ぎ、meta が仕様どおりになる', () => {
  const out = Migrate.convertRoom(ROOM1, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(Object.keys(out.groups), ['TESTMG']);
  assert.deepStrictEqual(out.groups.TESTMG.meta, {
    name: 'テスト旅行',
    createdAt: NOW,
    createdBy: UID,
    schemaVersion: 2,
    migratedFrom: 'rooms/TESTMG',
    migratedAt: NOW
  });
  assert.deepStrictEqual(out.order, ['TESTMG']);
});

test('members は ID キーのオブジェクトになり、order に並び順が入る', () => {
  const out = Migrate.convertRoom(ROOM1, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.members, {
    m1: { name: 'あ', order: 0 },
    m2: { name: 'い', order: 1 },
    m3: { name: 'う', order: 2 }
  });
});

test('payments が仕様どおりの形になる（settlementId/pending/createdBy つき）', () => {
  const out = Migrate.convertRoom(ROOM1, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.payments.p1, {
    date: '2026-08-01', memo: '宿', payerId: 'm1', amount: 30000,
    participants: { m1: true, m2: true, m3: true },
    settlementId: null, pending: false,
    createdBy: UID, createdAt: NOW, updatedAt: NOW
  });
  assert.strictEqual(Object.keys(out.groups.TESTMG.payments).length, 2);
});

test('変換後の残高・清算が変換前（v1 の形）と 1 円も変わらない', () => {
  const out = Migrate.convertRoom(ROOM1, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  const before = Calc.calcSettlement(ROOM1.groups[0].members, ROOM1.payments);
  const after = Calc.calcSettlement(out.groups.TESTMG.members, out.groups.TESTMG.payments);
  assert.deepStrictEqual(
    after.map(t => [t.from, t.to, t.amount]),
    before.map(t => [t.from, t.to, t.amount]));
  const balBefore = Calc.calcBalances(ROOM1.groups[0].members, ROOM1.payments);
  const balAfter = Calc.calcBalances(out.groups.TESTMG.members, out.groups.TESTMG.payments);
  assert.deepStrictEqual(balAfter, balBefore);
});

// ---------------------------------------------------------------- ケース②
console.log('ケース②: 3 グループ混在');

const ROOM3 = {
  groups: [
    { id: 'gA', name: 'A会', members: [{ id: 'a1', name: 'A1' }, { id: 'a2', name: 'A2' }] },
    { id: 'gB', name: 'B会', members: [{ id: 'b1', name: 'B1' }, { id: 'b2', name: 'B2' }] },
    { id: 'gC', name: 'C会', members: [{ id: 'c1', name: 'C1' }, { id: 'c2', name: 'C2' }] }
  ],
  payments: [
    { id: 'pa', groupId: 'gA', date: '2026-01-01', memo: '', payerId: 'a1', amount: 1000, participants: ['a1', 'a2'] },
    { id: 'pb', groupId: 'gB', date: '2026-01-02', memo: '', payerId: 'b1', amount: 2000, participants: ['b1', 'b2'] },
    { id: 'pc', groupId: 'gC', date: '2026-01-03', memo: '', payerId: 'c1', amount: 3000, participants: ['c1', 'c2'] }
  ]
};

test('pickGroupId のグループが元のコードを受け取る', () => {
  const out = Migrate.convertRoom(ROOM3,
    { code: 'TESTMG', uid: UID, pickGroupId: 'gB', newCodes: ['NEW001', 'NEW002'], now: NOW });
  assert.strictEqual(out.groups.TESTMG.meta.name, 'B会');
  assert.strictEqual(out.order[0], 'TESTMG');
});

test('残りのグループに newCodes が順番どおり配られる', () => {
  const out = Migrate.convertRoom(ROOM3,
    { code: 'TESTMG', uid: UID, pickGroupId: 'gB', newCodes: ['NEW001', 'NEW002'], now: NOW });
  assert.deepStrictEqual(out.order, ['TESTMG', 'NEW001', 'NEW002']);
  assert.strictEqual(out.groups.NEW001.meta.name, 'A会');   // 元の並び順は保たれる
  assert.strictEqual(out.groups.NEW002.meta.name, 'C会');
});

test('支払いがグループごとに正しく振り分けられる', () => {
  const out = Migrate.convertRoom(ROOM3,
    { code: 'TESTMG', uid: UID, pickGroupId: 'gB', newCodes: ['NEW001', 'NEW002'], now: NOW });
  assert.deepStrictEqual(Object.keys(out.groups.TESTMG.payments), ['pb']);
  assert.deepStrictEqual(Object.keys(out.groups.NEW001.payments), ['pa']);
  assert.deepStrictEqual(Object.keys(out.groups.NEW002.payments), ['pc']);
  assert.strictEqual(out.groups.TESTMG.payments.pb.amount, 2000);
});

test('どのグループにも属さない支払いが混ざらない（グループ間の漏れが無い）', () => {
  const out = Migrate.convertRoom(ROOM3,
    { code: 'TESTMG', uid: UID, pickGroupId: 'gA', newCodes: ['NEW001', 'NEW002'], now: NOW });
  Object.keys(out.groups).forEach(code => {
    const g = out.groups[code];
    Object.keys(g.payments).forEach(pid => {
      const p = g.payments[pid];
      assert.ok(Object.prototype.hasOwnProperty.call(g.members, p.payerId),
        code + ' の ' + pid + ' の支払者がメンバーに居ない');
    });
  });
});

test('pickGroupId が無い・見つからないときは先頭のグループが引き継ぐ', () => {
  const a = Migrate.convertRoom(ROOM3, { code: 'TESTMG', uid: UID, newCodes: ['N1', 'N2'], now: NOW });
  assert.strictEqual(a.groups.TESTMG.meta.name, 'A会');
  const b = Migrate.convertRoom(ROOM3, { code: 'TESTMG', uid: UID, pickGroupId: 'nope', newCodes: ['N1', 'N2'], now: NOW });
  assert.strictEqual(b.groups.TESTMG.meta.name, 'A会');
});

test('新コードが足りないときは落ちず、足りない数を数える', () => {
  const out = Migrate.convertRoom(ROOM3, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.order, ['TESTMG']);
  assert.strictEqual(out.skipped.noCodeGroups, 2);
});

// ---------------------------------------------------------------- ケース③
console.log('ケース③: 削除済みの除外');

const ROOM_DEL = {
  groups: [
    { id: 'g1', name: '生きてる会', members: [{ id: 'm1', name: 'あ' }, { id: 'm2', name: 'い' }] },
    { id: 'g2', name: '消した会', members: [{ id: 'n1', name: 'か' }] }
  ],
  payments: [
    { id: 'p1', groupId: 'g1', date: '2026-02-01', memo: '残る', payerId: 'm1', amount: 100, participants: ['m1', 'm2'] },
    { id: 'p2', groupId: 'g1', date: '2026-02-02', memo: '消した', payerId: 'm1', amount: 999, participants: ['m1', 'm2'] },
    { id: 'p3', groupId: 'g2', date: '2026-02-03', memo: '消した会の支払い', payerId: 'n1', amount: 555, participants: ['n1'] }
  ],
  deletedGroupIds: ['g2'],
  deletedPaymentIds: ['p2']
};

test('deletedGroupIds のグループを取り込まない', () => {
  const out = Migrate.convertRoom(ROOM_DEL, { code: 'TESTMG', uid: UID, newCodes: ['N1'], now: NOW });
  assert.deepStrictEqual(out.order, ['TESTMG']);
  assert.strictEqual(out.groups.TESTMG.meta.name, '生きてる会');
  assert.strictEqual(out.skipped.deletedGroups, 1);
});

test('deletedPaymentIds の支払いを取り込まない', () => {
  const out = Migrate.convertRoom(ROOM_DEL, { code: 'TESTMG', uid: UID, newCodes: ['N1'], now: NOW });
  assert.deepStrictEqual(Object.keys(out.groups.TESTMG.payments), ['p1']);
  assert.strictEqual(out.skipped.deletedPayments, 1);
});

test('消したグループの支払いは孤児として除外される', () => {
  const out = Migrate.convertRoom(ROOM_DEL, { code: 'TESTMG', uid: UID, newCodes: ['N1'], now: NOW });
  assert.strictEqual(out.skipped.orphanPayments, 1);   // p3
});

// ---------------------------------------------------------------- ケース④
console.log('ケース④: 孤児支払い');

test('groupId が groups に無い支払いは取り込まず、件数だけ残す', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }] }],
    payments: [
      { id: 'p1', groupId: 'g1', date: '2026-03-01', memo: '', payerId: 'm1', amount: 10, participants: ['m1'] },
      { id: 'p2', groupId: 'g-nothing', date: '2026-03-02', memo: '迷子', payerId: 'x', amount: 20, participants: ['x'] },
      { id: 'p3', groupId: '', date: '2026-03-03', memo: 'groupId 無し', payerId: 'x', amount: 30, participants: [] }
    ]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(Object.keys(out.groups.TESTMG.payments), ['p1']);
  assert.strictEqual(out.skipped.orphanPayments, 2);
});

// ---------------------------------------------------------------- ケース⑤
console.log('ケース⑤: participants の変換');

test('participants の配列が {mid:true} になる', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }, { id: 'm2', name: 'い' }] }],
    payments: [{ id: 'p1', groupId: 'g1', date: '2026-04-01', memo: '', payerId: 'm1', amount: 100, participants: ['m1', 'm2'] }]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.payments.p1.participants, { m1: true, m2: true });
});

test('支払者が割り勘対象に入っていなくても足さない（v1 の挙動を保つ）', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }, { id: 'm2', name: 'い' }] }],
    payments: [{ id: 'p1', groupId: 'g1', date: '2026-04-01', memo: '', payerId: 'm1', amount: 300, participants: ['m2'] }]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.payments.p1.participants, { m2: true });
  const bal = Calc.calcBalances(out.groups.TESTMG.members, out.groups.TESTMG.payments);
  assert.strictEqual(bal.m1, 0);      // v1 と同じく支払者には加算されない
  assert.strictEqual(bal.m2, -300);
});

test('participants が空・未定義でも落ちない（対象 0 人として取り込む）', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }] }],
    payments: [
      { id: 'p1', groupId: 'g1', date: '2026-04-02', memo: '', payerId: 'm1', amount: 100, participants: [] },
      { id: 'p2', groupId: 'g1', date: '2026-04-03', memo: '', payerId: 'm1', amount: 100 }
    ]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.payments.p1.participants, {});
  assert.deepStrictEqual(out.groups.TESTMG.payments.p2.participants, {});
});

test('金額は整数円に丸める', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }] }],
    payments: [
      { id: 'p1', groupId: 'g1', date: '2026-04-04', memo: '', payerId: 'm1', amount: 1234.6, participants: ['m1'] },
      { id: 'p2', groupId: 'g1', date: '2026-04-05', memo: '', payerId: 'm1', amount: '2500', participants: ['m1'] },
      { id: 'p3', groupId: 'g1', date: '2026-04-06', memo: '', payerId: 'm1', amount: 'こわれた', participants: ['m1'] }
    ]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.strictEqual(out.groups.TESTMG.payments.p1.amount, 1235);
  assert.strictEqual(out.groups.TESTMG.payments.p2.amount, 2500);
  assert.strictEqual(out.groups.TESTMG.payments.p3.amount, 0);
});

// ---------------------------------------------------------------- ケース⑥
console.log('ケース⑥: 壊れた入力');

test('groups が無い / 空でも落ちず、結果も空', () => {
  [undefined, null, {}, { groups: [] }, { payments: [] }, 'こわれた', 42].forEach(bad => {
    const out = Migrate.convertRoom(bad, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
    assert.deepStrictEqual(out.groups, {});
    assert.deepStrictEqual(out.order, []);
  });
});

test('payments が無くてもグループだけ取り込む', () => {
  const out = Migrate.convertRoom(
    { groups: [{ id: 'g1', name: 'A', members: [{ id: 'm1', name: 'あ' }] }] },
    { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(out.groups.TESTMG.payments, {});
  assert.strictEqual(out.groups.TESTMG.meta.name, 'A');
});

test('groups / payments の中に null や壊れた要素が混ざっても落ちない', () => {
  const room = {
    groups: [null, { id: 'g1', name: 'A', members: [null, { id: 'm1', name: 'あ' }, 'ごみ'] }, 'ごみ'],
    payments: [null, 'ごみ', { id: 'p1', groupId: 'g1', date: '2026-05-01', memo: '', payerId: 'm1', amount: 50, participants: ['m1'] }]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.deepStrictEqual(Object.keys(out.groups.TESTMG.members), ['m1']);
  assert.deepStrictEqual(Object.keys(out.groups.TESTMG.payments), ['p1']);
});

test('名前が空でも既定の名前が入る', () => {
  const out = Migrate.convertRoom(
    { groups: [{ id: 'g1', members: [{ id: 'm1' }] }] },
    { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  assert.strictEqual(out.groups.TESTMG.meta.name, '(名称未設定)');
  assert.strictEqual(out.groups.TESTMG.members.m1.name, '(名前なし)');
});

test('Firebase のキーに使えない ID は振り直し、支払いの参照も差し替える', () => {
  const room = {
    groups: [{ id: 'g1', name: 'A', members: [{ id: 'a.b', name: 'ドット' }, { id: 'ok1', name: '普通' }] }],
    payments: [{ id: 'p/1', groupId: 'g1', date: '2026-06-01', memo: '', payerId: 'a.b', amount: 200, participants: ['a.b', 'ok1'] }]
  };
  const out = Migrate.convertRoom(room, { code: 'TESTMG', uid: UID, newCodes: [], now: NOW });
  const mids = Object.keys(out.groups.TESTMG.members);
  const pids = Object.keys(out.groups.TESTMG.payments);
  mids.forEach(k => assert.ok(Migrate.isSafeKey(k), 'メンバー ID が使えない文字を含む: ' + k));
  pids.forEach(k => assert.ok(Migrate.isSafeKey(k), '支払い ID が使えない文字を含む: ' + k));
  const p = out.groups.TESTMG.payments[pids[0]];
  assert.ok(mids.indexOf(p.payerId) >= 0, '支払者の参照が差し替わっていない');
  assert.deepStrictEqual(Object.keys(p.participants).sort(), mids.slice().sort());
});

// ---------------------------------------------------------------- 要約
console.log('summarizeRoom（選択ダイアログ用）');

test('グループ名・メンバー数・支払い件数と除外件数を返す', () => {
  const s = Migrate.summarizeRoom(ROOM_DEL);
  assert.deepStrictEqual(s.groups, [
    { id: 'g1', name: '生きてる会', memberCount: 2, paymentCount: 1 }
  ]);
  assert.deepStrictEqual(s.skipped, { deletedGroups: 1, deletedPayments: 1, orphanPayments: 1 });
});

test('countGroups が取り込むグループ数を返す（必要な新コード数 = これ - 1）', () => {
  assert.strictEqual(Migrate.countGroups(ROOM3), 3);
  assert.strictEqual(Migrate.countGroups(ROOM_DEL), 1);
  assert.strictEqual(Migrate.countGroups(null), 0);
});

test('壊れた入力でも summarizeRoom が落ちない', () => {
  [undefined, null, {}, 'ごみ', { groups: 'ごみ' }].forEach(bad => {
    const s = Migrate.summarizeRoom(bad);
    assert.deepStrictEqual(s.groups, []);
  });
});

// ----------------------------------------------------------------
console.log('');
if (failures.length === 0) {
  console.log('すべて通過: ' + passed + ' 件');
  process.exit(0);
} else {
  console.log('失敗 ' + failures.length + ' 件 / 通過 ' + passed + ' 件');
  process.exit(1);
}
