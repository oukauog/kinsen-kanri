/*
 * tests/authdomain.test.js — 認証ドメインの選び方の固定テスト
 * 実行: node tests/authdomain.test.js
 *
 * 背景（工事1-2 で直した不具合）:
 *   iPhone Safari で「Google でログイン」を押すと kinsen-kanri.firebaseapp.com に
 *   飛んだまま "Unable to process request due to missing initial state." で止まった。
 *   アプリの配信元（*.vercel.app）と authDomain（firebaseapp.com）が別サイトなので、
 *   Safari のストレージ分離でリダイレクト認証の途中状態が引き継げないため。
 *
 *   対策は Firebase 公式の Option 3（自分のドメインで /__/auth/* を受けて
 *   firebaseapp.com へプロキシする）。vercel.json の rewrites と、
 *   ここでテストしている authDomain の切替がセットで効く。
 *
 * このテストが落ちる = iPhone Safari のログインが再び壊れる、と思ってよい。
 */
'use strict';

const assert = require('assert');
const FI = require('../js/firebase-init.js');

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

const FALLBACK = 'kinsen-kanri.firebaseapp.com';

console.log('authDomain の切替');

test('定数が仕様どおり（従来の authDomain）', () => {
  assert.strictEqual(FI.FALLBACK_AUTH_DOMAIN, FALLBACK);
});

test('本番の vercel.app では自分のホストを使う', () => {
  assert.strictEqual(FI.pickAuthDomain('kinsen-kanri.vercel.app'), 'kinsen-kanri.vercel.app');
});

test('プレビューの vercel.app でも自分のホストを使う', () => {
  assert.strictEqual(
    FI.pickAuthDomain('kinsen-kanri-git-v2-oukauog.vercel.app'),
    'kinsen-kanri-git-v2-oukauog.vercel.app');
});

test('大文字が混ざっていても vercel.app と判定する', () => {
  assert.strictEqual(FI.pickAuthDomain('Kinsen-Kanri.Vercel.App'), 'Kinsen-Kanri.Vercel.App');
});

test('localhost は従来どおり firebaseapp.com（プロキシが無いため）', () => {
  assert.strictEqual(FI.pickAuthDomain('localhost'), FALLBACK);
});

test('127.0.0.1 も従来どおり', () => {
  assert.strictEqual(FI.pickAuthDomain('127.0.0.1'), FALLBACK);
});

test('vercel.app に見せかけた別ドメインは従来どおり', () => {
  assert.strictEqual(FI.pickAuthDomain('vercel.app.example.com'), FALLBACK);
  assert.strictEqual(FI.pickAuthDomain('notvercel.app'), FALLBACK);
});

test('ホスト名が空・未定義でも落ちずに従来どおり', () => {
  assert.strictEqual(FI.pickAuthDomain(''), FALLBACK);
  assert.strictEqual(FI.pickAuthDomain(undefined), FALLBACK);
  assert.strictEqual(FI.pickAuthDomain(null), FALLBACK);
});

console.log('');
if (failures.length === 0) {
  console.log('すべて通過: ' + passed + ' 件');
  process.exit(0);
} else {
  console.log('失敗 ' + failures.length + ' 件 / 通過 ' + passed + ' 件');
  process.exit(1);
}
