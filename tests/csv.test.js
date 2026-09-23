/*
 * tests/csv.test.js — CSV 出力の固定テスト（工事4a）
 * 実行: node tests/csv.test.js（まとめては node tests/run_all.js）
 *
 * Excel で開けること（BOM）、列の順、清算状態の 3 種、
 * 未清算/累計の切替が変わらないことを固定する。
 */
'use strict';

const assert = require('assert');
const Csv = require('../js/csv.js');

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

/** BOM を外して行に分ける */
function lines(csv) {
  assert.strictEqual(csv.charCodeAt(0), 0xFEFF, '先頭が BOM でない');
  return csv.slice(1).replace(/\r\n$/, '').split('\r\n');
}

const GROUP = {
  meta: { name: 'テスト旅行' },
  members: {
    m1: { name: 'あ', order: 0 },
    m2: { name: 'い', order: 1 },
    m3: { name: 'う', order: 2 }
  }
};

const SETTLEMENTS = {
  s1: { createdAt: new Date(2026, 8, 20, 18, 30).getTime() }   // 2026/09/20 18:30
};

const PAYMENTS = {
  p1: {
    date: '2026-09-01', memo: '宿代', payerId: 'm1', amount: 3000,
    participants: { m1: true, m2: true, m3: true },
    settlementId: null, pending: false, createdAt: 100
  },
  p2: {
    date: '2026-09-03', memo: '昼食', payerId: 'm2', amount: 1500,
    participants: { m1: true, m2: true },
    settlementId: 's1', pending: false, createdAt: 200
  },
  p3: {
    date: '2026-09-02', memo: 'おみやげ', payerId: 'm3', amount: 0,
    participants: { m1: true, m2: true, m3: true },
    settlementId: null, pending: true, createdAt: 300
  }
};

// =====================================================================
console.log('escapeCell');

test('普通の値はそのまま', () => {
  assert.strictEqual(Csv.escapeCell('あ'), 'あ');
  assert.strictEqual(Csv.escapeCell(1234), '1234');
  assert.strictEqual(Csv.escapeCell(''), '');
});

test('null / undefined は空文字', () => {
  assert.strictEqual(Csv.escapeCell(null), '');
  assert.strictEqual(Csv.escapeCell(undefined), '');
});

test('カンマを含むと囲む', () => {
  assert.strictEqual(Csv.escapeCell('あ,い'), '"あ,い"');
});

test('改行を含むと囲む（CR も LF も）', () => {
  assert.strictEqual(Csv.escapeCell('あ\nい'), '"あ\nい"');
  assert.strictEqual(Csv.escapeCell('あ\r\nい'), '"あ\r\nい"');
});

test('ダブルクォートは "" にして囲む', () => {
  assert.strictEqual(Csv.escapeCell('あ"い'), '"あ""い"');
  assert.strictEqual(Csv.escapeCell('"'), '""""');
});

// =====================================================================
console.log('paymentsCsv');

test('先頭に BOM が付く', () => {
  assert.strictEqual(Csv.paymentsCsv(GROUP, PAYMENTS, SETTLEMENTS).charCodeAt(0), 0xFEFF);
});

test('ヘッダの列が仕様どおり', () => {
  const l = lines(Csv.paymentsCsv(GROUP, PAYMENTS, SETTLEMENTS));
  assert.strictEqual(l[0], '日付,メモ,支払った人,金額,割り勘対象,1人あたり,清算状態');
});

test('並びは画面と同じ（日付の降順）', () => {
  const l = lines(Csv.paymentsCsv(GROUP, PAYMENTS, SETTLEMENTS));
  assert.deepStrictEqual(
    l.slice(1).map(r => r.split(',')[0]),
    ['2026-09-03', '2026-09-02', '2026-09-01']);
});

test('割り勘対象は名前を「・」で連結、1人あたりは四捨五入', () => {
  const l = lines(Csv.paymentsCsv(GROUP, PAYMENTS, SETTLEMENTS));
  const row = l.find(r => r.indexOf('宿代') >= 0).split(',');
  assert.strictEqual(row[2], 'あ');          // 支払った人
  assert.strictEqual(row[3], '3000');        // 金額
  assert.strictEqual(row[4], 'あ・い・う');   // 割り勘対象
  assert.strictEqual(row[5], '1000');        // 1人あたり
});

test('清算状態 3 種（未清算 / 清算済み（日時）/ 金額確認中）', () => {
  const l = lines(Csv.paymentsCsv(GROUP, PAYMENTS, SETTLEMENTS));
  const get = memo => l.find(r => r.indexOf(memo) >= 0).split(',').pop();
  assert.strictEqual(get('宿代'), '未清算');
  assert.strictEqual(get('昼食'), '清算済み（2026/09/20 18:30）');
  assert.strictEqual(get('おみやげ'), '金額確認中');
});

test('清算レコードが見つからないときは日時なしの「清算済み」', () => {
  const l = lines(Csv.paymentsCsv(GROUP, PAYMENTS, {}));
  assert.strictEqual(l.find(r => r.indexOf('昼食') >= 0).split(',').pop(), '清算済み');
});

test('メモにカンマや引用符が入っても列がずれない', () => {
  const pays = {
    px: {
      date: '2026-09-05', memo: '居酒屋,2次会「"乾杯"」', payerId: 'm1', amount: 1000,
      participants: { m1: true, m2: true }, settlementId: null, pending: false, createdAt: 1
    }
  };
  const l = lines(Csv.paymentsCsv(GROUP, pays, {}));
  assert.strictEqual(l[1],
    '2026-09-05,"居酒屋,2次会「""乾杯""」",あ,1000,あ・い,500,未清算');
});

test('支払いが 0 件ならヘッダだけ', () => {
  const l = lines(Csv.paymentsCsv(GROUP, {}, {}));
  assert.strictEqual(l.length, 1);
  assert.strictEqual(l[0], '日付,メモ,支払った人,金額,割り勘対象,1人あたり,清算状態');
});

test('いないメンバーを指す支払いでも落ちない（? と出す）', () => {
  const pays = {
    px: {
      date: '2026-09-06', memo: 'なぞ', payerId: 'zzz', amount: 100,
      participants: { zzz: true }, settlementId: null, pending: false, createdAt: 1
    }
  };
  const l = lines(Csv.paymentsCsv(GROUP, pays, {}));
  assert.strictEqual(l[1], '2026-09-06,なぞ,?,100,?,100,未清算');
});

// =====================================================================
console.log('balancesCsv');

test('先頭に BOM、1 行目はモードのコメント行', () => {
  const a = Csv.balancesCsv(GROUP, PAYMENTS, 'unsettled');
  assert.strictEqual(a.charCodeAt(0), 0xFEFF);
  assert.strictEqual(lines(a)[0], '# 残高（未清算のみ）');
  assert.strictEqual(lines(Csv.balancesCsv(GROUP, PAYMENTS, 'all'))[0], '# 残高（累計）');
});

test('ヘッダの列が仕様どおり', () => {
  assert.strictEqual(lines(Csv.balancesCsv(GROUP, PAYMENTS, 'unsettled'))[1],
    'メンバー,払った合計,負担分,残高');
});

test('未清算のみ: 清算済みと確認中を除いて計算する', () => {
  // 未清算の対象は p1（あ が 3000 を 3 人で）だけ
  const l = lines(Csv.balancesCsv(GROUP, PAYMENTS, 'unsettled'));
  const rows = l.slice(2).map(r => r.split(','));
  const byName = {};
  rows.forEach(r => { byName[r[0]] = r; });
  assert.deepStrictEqual(byName['あ'], ['あ', '3000', '1000', '2000']);
  assert.deepStrictEqual(byName['い'], ['い', '0', '1000', '-1000']);
  assert.deepStrictEqual(byName['う'], ['う', '0', '1000', '-1000']);
});

test('累計: 清算済みも含める（確認中は除く）', () => {
  // p1（3000 を 3 人）＋ p2（い が 1500 を あ・い で）
  const l = lines(Csv.balancesCsv(GROUP, PAYMENTS, 'all'));
  const byName = {};
  l.slice(2).forEach(r => { const c = r.split(','); byName[c[0]] = c; });
  assert.deepStrictEqual(byName['あ'], ['あ', '3000', '1750', '1250']);
  assert.deepStrictEqual(byName['い'], ['い', '1500', '1750', '-250']);
  assert.deepStrictEqual(byName['う'], ['う', '0', '1000', '-1000']);
});

test('モードを省略すると未清算のみ', () => {
  assert.strictEqual(lines(Csv.balancesCsv(GROUP, PAYMENTS))[0], '# 残高（未清算のみ）');
});

test('並びはマイナスが大きい人から（画面の残高カードと同じ）', () => {
  const l = lines(Csv.balancesCsv(GROUP, PAYMENTS, 'unsettled'));
  const names = l.slice(2).map(r => r.split(',')[0]);
  assert.strictEqual(names[names.length - 1], 'あ', '最後が一番多く払っている人');
});

test('支払いが 0 件でもメンバー行は 0 で出る', () => {
  const l = lines(Csv.balancesCsv(GROUP, {}, 'unsettled'));
  assert.strictEqual(l.length, 2 + 3);
  l.slice(2).forEach(r => {
    const c = r.split(',');
    assert.deepStrictEqual(c.slice(1), ['0', '0', '0'], r);
  });
});

test('確認中しか無ければ全員 0（どちらのモードでも）', () => {
  const pays = { p: PAYMENTS.p3 };
  ['unsettled', 'all'].forEach(mode => {
    lines(Csv.balancesCsv(GROUP, pays, mode)).slice(2).forEach(r => {
      assert.deepStrictEqual(r.split(',').slice(1), ['0', '0', '0'], mode + ': ' + r);
    });
  });
});

test('メンバー名にカンマが入っても列がずれない', () => {
  const g = { members: { m1: { name: 'あ,い', order: 0 }, m2: { name: 'う', order: 1 } } };
  const l = lines(Csv.balancesCsv(g, {}, 'unsettled'));
  assert.strictEqual(l[2].indexOf('"あ,い"'), 0);
});

// =====================================================================
console.log('ファイル名の小道具');

test('safeFileName が使えない文字を置き換える', () => {
  assert.strictEqual(Csv.safeFileName('テスト/旅行:2026'), 'テスト_旅行_2026');
  assert.strictEqual(Csv.safeFileName('あ い'), 'あ_い');
  assert.strictEqual(Csv.safeFileName(null), '');
});

test('stamp が YYYYMMDD', () => {
  assert.strictEqual(Csv.stamp(new Date(2026, 8, 24)), '20260924');
  assert.strictEqual(Csv.stamp(new Date(2026, 11, 5)), '20261205');
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
