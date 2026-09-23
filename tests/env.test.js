/*
 * tests/env.test.js — アプリ内ブラウザ判定の固定テスト（工事4a）
 * 実行: node tests/env.test.js（まとめては node tests/run_all.js）
 *
 * ここが崩れると「LINE で開いたのに案内が出ない（ログインできず詰む）」か
 * 「普通の Safari なのに案内が出る（うるさい）」のどちらかになる。
 * 誤判定に備えてログインボタン自体は常に出しているので、
 * 案内が出ないより出る方が安全側。
 */
'use strict';

const assert = require('assert');
const Env = require('../js/env.js');

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

const UA = {
  lineIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Line/14.5.0 NetType/WIFI Language/ja',
  lineAndroid: 'Mozilla/5.0 (Linux; Android 14; SM-S911 Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.6261.119 Mobile Safari/537.36 Line/14.5.0',
  discordAndroid: 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36 Discord/158.0',
  instagramIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 320.0.0.23.104 (iPhone14,5; iOS 17_5)',
  facebookIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/456.0.0.32.108]',
  twitterAndroid: 'Mozilla/5.0 (Linux; Android 13; SM-A536 Build/TP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36 TwitterAndroid',
  wechatIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.44(0x18002c2b)',
  androidWebView: 'Mozilla/5.0 (Linux; Android 12; M2101K6G Build/SKQ1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/108.0.5359.128 Mobile Safari/537.36',

  safariIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  chromeIOS: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/122.0.6261.89 Mobile/15E148 Safari/604.1',
  chromeAndroid: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
  chromePC: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  firefoxPC: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
  safariMac: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15'
};

console.log('アプリ内ブラウザ（案内を出す）');

[
  ['LINE（iOS）', UA.lineIOS],
  ['LINE（Android）', UA.lineAndroid],
  ['Discord（Android）', UA.discordAndroid],
  ['Instagram（iOS）', UA.instagramIOS],
  ['Facebook / Messenger（iOS）', UA.facebookIOS],
  ['X / Twitter（Android）', UA.twitterAndroid],
  ['WeChat（iOS）', UA.wechatIOS],
  ['Android の WebView（; wv）', UA.androidWebView]
].forEach(function (pair) {
  test(pair[0] + ' は true', () => {
    assert.strictEqual(Env.isInAppBrowser(pair[1]), true);
  });
});

console.log('普通のブラウザ（案内を出さない）');

[
  ['Safari（iOS）', UA.safariIOS],
  ['Chrome（iOS）', UA.chromeIOS],
  ['Chrome（Android）', UA.chromeAndroid],
  ['Chrome（PC）', UA.chromePC],
  ['Firefox（PC）', UA.firefoxPC],
  ['Safari（Mac）', UA.safariMac]
].forEach(function (pair) {
  test(pair[0] + ' は false', () => {
    assert.strictEqual(Env.isInAppBrowser(pair[1]), false);
  });
});

console.log('こわれた入力');

test('空・null・undefined は false（案内を出さない）', () => {
  assert.strictEqual(Env.isInAppBrowser(''), false);
  assert.strictEqual(Env.isInAppBrowser(null), false);
  assert.strictEqual(Env.isInAppBrowser(undefined), false);
});

test('文字列でなくても落ちない', () => {
  assert.strictEqual(Env.isInAppBrowser(123), false);
  assert.strictEqual(Env.isInAppBrowser({}), false);
});

console.log('');
if (failures.length === 0) {
  console.log('すべて通過: ' + passed + ' 件');
  process.exit(0);
} else {
  console.log('失敗 ' + failures.length + ' 件 / 通過 ' + passed + ' 件');
  process.exit(1);
}
