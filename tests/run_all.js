/*
 * tests/run_all.js — tests/*.test.js をまとめて実行する
 * 実行: node tests/run_all.js
 *
 * 1 つでも失敗したら終了コード 1。
 * 新しいテストは tests/ に <名前>.test.js として置けば自動で拾われる
 * （ブラウザで動かす ui_smoke_*.js は .test.js ではないので拾われない）。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const dir = __dirname;
const files = fs.readdirSync(dir)
  .filter(f => f.endsWith('.test.js'))
  .sort();

if (files.length === 0) {
  console.log('テストが 1 つもありません');
  process.exit(1);
}

const results = [];

files.forEach(f => {
  console.log('=== ' + f + ' ===');
  const r = spawnSync(process.execPath, [path.join(dir, f)], { stdio: 'inherit' });
  results.push({ file: f, code: r.status });
  console.log('');
});

const failed = results.filter(r => r.code !== 0);

console.log('==================================================');
results.forEach(r => {
  console.log((r.code === 0 ? '通過   ' : '失敗   ') + r.file);
});
console.log('--------------------------------------------------');
if (failed.length === 0) {
  console.log('すべてのテストファイルが通過しました（' + results.length + ' ファイル）');
  process.exit(0);
} else {
  console.log('失敗 ' + failed.length + ' ファイル / 全 ' + results.length + ' ファイル');
  process.exit(1);
}
