# -*- coding: utf-8 -*-
"""
工事4c-2: 画面の通し確認に「入力欄の寸法が揃っていること」の確認を足す。

確認すること:
  ・幅 390px（iPhone 相当）で、#payDate / #payMemo / #payAmount / #payPayer の
    getBoundingClientRect() の height と width がすべて一致すること（±1px）
  ・幅 1024px（PC 相当）では日付欄とメモ欄の高さが等しいこと（工事4c 以前と同じ）

注意:
  ヘッドレス Chrome では iOS 固有の描画差は再現できない。
  ここで見られるのは「Chrome で崩していないこと」まで。
  iOS 実機での揃い方の判定は花井が行う。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_datefix_4c2.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

BEFORE = """      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""

AFTER = """      // ══ 工事4c-2: 入力欄の寸法が揃っていること ══
      .then(function () {
        // 幅を変えて @media を効かせるため、同じページを iframe に読み込んで測る。
        // ※ iOS 固有の描画差はヘッドレス Chrome では出ない。ここは「崩していない」確認。
        function rects(width) {
          return new Promise(function (resolve) {
            var f = document.createElement('iframe');
            f.style.cssText = 'position:fixed;left:-9999px;top:0;height:900px;border:0';
            f.style.width = width + 'px';
            f.src = location.pathname;
            f.onload = function () {
              var d = f.contentDocument;
              // 支払いモーダルを開いた状態にして測る（非表示だと寸法が 0 になるため）
              var ov = d.getElementById('paymentModal');
              if (ov) ov.classList.add('open');
              var out = {};
              ['payDate', 'payMemo', 'payAmount', 'payPayer'].forEach(function (id) {
                var el = d.getElementById(id);
                var r = el ? el.getBoundingClientRect() : null;
                out[id] = r ? { h: Math.round(r.height * 10) / 10, w: Math.round(r.width * 10) / 10 }
                  : null;
              });
              f.remove();
              resolve(out);
            };
            document.body.appendChild(f);
          });
        }
        var near = function (a, b) { return Math.abs(a - b) <= 1; };

        return rects(390).then(function (m) {
          var ids = ['payDate', 'payMemo', 'payAmount', 'payPayer'];
          var missing = ids.filter(function (id) { return !m[id]; });
          check('スマホ幅: 4 つの入力欄が測れる', missing.length === 0, missing.join(','));
          if (missing.length) return rects(1024);

          var hs = ids.map(function (id) { return m[id].h; });
          var ws = ids.map(function (id) { return m[id].w; });
          var desc = ids.map(function (id) {
            return id + '=' + m[id].h + 'x' + m[id].w;
          }).join(' / ');

          check('スマホ幅: 日付欄の高さが他の欄と揃う（4 欄が同じ高さ）',
            hs.every(function (h) { return near(h, hs[0]); }), desc);
          check('スマホ幅: 4 欄の幅が揃う',
            ws.every(function (w) { return near(w, ws[0]); }), desc);
          check('スマホ幅: 高さが 40px になっている', near(hs[0], 40), '高さ=' + hs[0]);
          return rects(1024);
        }).then(function (m) {
          if (!m.payDate || !m.payMemo) {
            check('PC 幅: 日付欄とメモ欄の高さが等しい', false, '測れなかった');
            return;
          }
          check('PC 幅: 日付欄とメモ欄の高さが等しい（工事4c 以前と同じ）',
            near(m.payDate.h, m.payMemo.h),
            'date=' + m.payDate.h + ' / memo=' + m.payMemo.h);
          check('PC 幅: 高さを 40px に固定していない（PC は従来のまま）',
            !near(m.payDate.h, 40), '高さ=' + m.payDate.h);
        });
      })

      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',
          $('loginScreen').hidden === false && $('appLayout').hidden === true);"""


def main():
    with io.open(DRIVER, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "日付欄の高さが他の欄と揃う" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    before, after = fix(BEFORE), fix(AFTER)
    n = src.count(before)
    if n != 1:
        print("中止しました（一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1

    with io.open(DRIVER, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(before, after, 1))
    print("書き込み完了: " + DRIVER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
