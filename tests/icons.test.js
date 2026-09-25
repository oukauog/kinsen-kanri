/*
 * tests/icons.test.js — ホーム画面アイコン・favicon・manifest の固定テスト（工事7）
 * 実行: node tests/icons.test.js（まとめては node tests/run_all.js）
 *
 * ここが通る = 「アイコンの原本（SVG）と PNG 4 枚・site.webmanifest があり、寸法が正しく、
 * index.html の head から 6 つのタグで参照され、全画面モード（apple-mobile-web-app-capable）は付いていない」。
 * PNG の寸法は外部ライブラリを使わず、IHDR（先頭 8 バイトの署名の後、16 バイト目から幅・高さ 各 4 バイト、
 * ビッグエンディアン）を読んで見る。
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const read = p => fs.readFileSync(path.join(ROOT, p));
const readText = p => fs.readFileSync(path.join(ROOT, p), 'utf8');

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

const PNG_SIG = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

/** PNG の IHDR から { width, height, colorType } を読む */
function pngInfo(buf) {
  assert.ok(buf.length >= 33, 'PNG が短すぎる');
  assert.ok(buf.subarray(0, 8).equals(PNG_SIG), 'PNG の署名ではない');
  assert.strictEqual(buf.toString('ascii', 12, 16), 'IHDR', '最初のチャンクが IHDR ではない');
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), colorType: buf[25] };
}

const PNGS = [
  ['icons/apple-touch-icon.png', 180],
  ['icons/icon-192.png', 192],
  ['icons/icon-512.png', 512],
  ['icons/favicon-32.png', 32]
];

// =====================================================================
console.log('ファイルがある');

['icons/icon.svg', 'site.webmanifest', 'index.html'].concat(PNGS.map(p => p[0])).forEach(p => {
  test(p + ' がある', () => {
    assert.ok(fs.existsSync(path.join(ROOT, p)), p + ' が無い');
  });
});

// =====================================================================
console.log('PNG の寸法');

PNGS.forEach(([p, n]) => {
  test(p + ' は ' + n + '×' + n + '、透明なしの RGB（カラータイプ 2）', () => {
    const info = pngInfo(read(p));
    assert.deepStrictEqual([info.width, info.height], [n, n]);
    assert.strictEqual(info.colorType, 2, 'カラータイプ ' + info.colorType + '（2 = RGB であるべき）');
  });
});

// =====================================================================
console.log('icon.svg');

test('icon.svg: viewBox="0 0 512 512" があり、width / height 属性は無い', () => {
  const svg = readText('icons/icon.svg');
  assert.ok(svg.indexOf('viewBox="0 0 512 512"') >= 0);
  const root = svg.match(/<svg\b[^>]*>/);
  assert.ok(root, '<svg> が無い');
  assert.ok(!/\swidth=/.test(root[0]) && !/\sheight=/.test(root[0]), root[0]);
});

test('icon.svg: fill="#4f46e5" の背景と、stroke="#ffffff"（または #fff）の線がある', () => {
  const svg = readText('icons/icon.svg');
  assert.ok(/fill="#4f46e5"/i.test(svg), '背景の fill が無い');
  assert.ok(/stroke="#(?:ffffff|fff)"/i.test(svg), '白い stroke が無い');
});

test('icon.svg: 文字（<text>）で描いていない', () => {
  assert.ok(!/<text\b/i.test(readText('icons/icon.svg')));
});

// =====================================================================
console.log('site.webmanifest');

test('site.webmanifest: JSON として読め、short_name は「金銭管理」、display は「browser」', () => {
  const m = JSON.parse(readText('site.webmanifest'));
  assert.strictEqual(m.short_name, '金銭管理');
  assert.strictEqual(m.display, 'browser');
});

test('site.webmanifest: icons に 192 と 512 の PNG がある', () => {
  const m = JSON.parse(readText('site.webmanifest'));
  const sizes = (m.icons || []).map(i => i.sizes + ' ' + i.type + ' ' + i.src).sort();
  assert.deepStrictEqual(sizes, [
    '192x192 image/png icons/icon-192.png',
    '512x512 image/png icons/icon-512.png'
  ]);
});

test('site.webmanifest: BOM が無い', () => {
  assert.ok(!read('site.webmanifest').subarray(0, 3).equals(Buffer.from([0xEF, 0xBB, 0xBF])));
});

// =====================================================================
console.log('index.html の head');

const TAGS = [
  '<link rel="icon" type="image/svg+xml" href="icons/icon.svg">',
  '<link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">',
  '<link rel="apple-touch-icon" sizes="180x180" href="icons/apple-touch-icon.png">',
  '<link rel="manifest" href="site.webmanifest">',
  '<meta name="theme-color" content="#4f46e5">',
  '<meta name="apple-mobile-web-app-title" content="金銭管理">'
];

function headOf() {
  const html = readText('index.html');
  const end = html.indexOf('</head>');
  assert.ok(end > 0, '</head> が無い');
  return html.slice(0, end);
}

TAGS.forEach(tag => {
  test('index.html の head に 1 つだけある: ' + tag, () => {
    const head = headOf();
    const n = head.split(tag).length - 1;
    assert.strictEqual(n, 1, n + ' 個');
  });
});

test('index.html に apple-mobile-web-app-capable が無い（全画面モードにしない）', () => {
  assert.ok(readText('index.html').indexOf('apple-mobile-web-app-capable') < 0);
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
