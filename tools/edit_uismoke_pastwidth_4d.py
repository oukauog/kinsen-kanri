# -*- coding: utf-8 -*-
"""
工事4d-B: 画面の通し確認に「スマホ幅で過去の清算の行がはみ出さないこと」の測定と確認を足す。

やること:
  ・名前の長めの 3 人のグループ（テスト横はみ出し）で清算を確定し、送金を全部チェック済みにする
    （「おふらいん → ものらる ✓ テスト太郎 09/25 09:16」の形になる）
  ・その「清算」モーダルの DOM を、幅 375px / 1024px の iframe に写して開き、
    モーダル本体（.modal）・.past-settlement・.transfer-row の scrollWidth / clientWidth と、
    モーダルの右端が画面内に収まっているかを測る
  ・測った数字は結果に「info」行として残す（報告書の表に使う）
  ・375px で、上の 3 つとも scrollWidth <= clientWidth、モーダルの右端 <= 画面幅 であることを確認する
  ・375px では「✓ 名前 日時」が名前の下の行に出ること、1024px では今までどおり同じ行であることを確認する
  ・1024px でも同じくはみ出さないことを確認する（PC の見た目を変えていないことの数字は info 行で比べる）

あわせて、測定用の iframe の中では通し確認そのものを走らせないようにする
（iframe の名前が kk-measure のときは run() を始めない）。

注意: ヘッドレス Chrome で測れるのは Chrome の描画まで。iOS Safari 固有の差は出ない。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_pastwidth_4d.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

EDITS = []

# ① 測定用 iframe の中では run() を始めない
EDITS.append(("""  function run() {
    var code = null;
""", """  function run() {
    var code = null;
    // 工事4d: 幅を測るための iframe（名前 kk-measure）の中では通し確認を走らせない
    if (window.name === 'kk-measure') return Promise.resolve();
"""))

# ② 測定と確認を、2 回目のログアウトの直前に足す
EDITS.append(("""      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',""",
"""      // ══ 工事4d-B: スマホ幅で過去の清算の行がはみ出さないこと ══
      .then(function () {
        root.KKStore._seedGroup('WIDE01', 'テスト横はみ出し', ['おふらいん', 'ものらる', 'm20nde']);
        return root.KKStore.joinGroup('WIDE01').then(function () { return wait(80); });
      })
      .then(function () {
        root.selectGroup('WIDE01');
        return wait(80);
      })
      .then(function () {
        root.openPaymentModal();
        $('payMemo').value = 'テスト幅の確認';
        $('payAmount').value = '123456';
        root.recordPayment();
        return wait(100);
      })
      .then(function () {
        root.openSettlement();
        return wait(60);
      })
      .then(function () { root.doConfirmSettlement(); return wait(150); })
      .then(function () {
        // 送金を全部チェック済みにする（✓ 名前 日時 が付いた行にする）
        var g = root.KKStore._data.groups.WIDE01;
        var sid = Object.keys(g.settlements)[0];
        var tids = Object.keys(g.settlements[sid].transfers);
        check('幅の確認用: 送金が 2 本ある', tids.length === 2, tids.length + ' 本');
        tids.forEach(function (tid) { root.toggleTransferDone(sid, tid, true); });
        return wait(150);
      })
      .then(function () {
        var rows = $('settlementContent').querySelectorAll('.transfer-row.done .transfer-by');
        check('幅の確認用: チェック済みで名前と日時が付いた行がある', rows.length === 2,
          rows.length + ' 行');

        // 開いている「清算」モーダルの DOM を、幅を変えた iframe に写して測る
        var html = $('settlementModal').outerHTML;
        function measure(width) {
          return new Promise(function (resolve) {
            var f = document.createElement('iframe');
            f.name = 'kk-measure';
            f.style.cssText = 'position:fixed;left:-9999px;top:0;height:800px;border:0';
            f.style.width = width + 'px';
            f.src = location.pathname;
            f.onload = function () {
              var d = f.contentDocument;
              var w = f.contentWindow;
              d.getElementById('settlementModal').outerHTML = html;
              var ov = d.getElementById('settlementModal');
              ov.classList.add('open');
              var sw = function (el) {
                return el ? { sw: el.scrollWidth, cw: el.clientWidth } : { sw: -1, cw: -1 };
              };
              // 行は複数あるので、いちばんはみ出しの大きいものを代表にする
              var worst = function (sel) {
                var best = null;
                Array.prototype.forEach.call(ov.querySelectorAll(sel), function (el) {
                  var v = sw(el);
                  if (!best || v.sw - v.cw > best.sw - best.cw) best = v;
                });
                return best || { sw: -1, cw: -1 };
              };
              var modal = ov.querySelector('.modal');
              var r = modal.getBoundingClientRect();
              var out = {
                width: width,
                vw: w.innerWidth,
                modal: sw(modal),
                past: worst('.past-settlement'),
                row: worst('.transfer-row'),
                names: worst('.transfer-names'),
                modalLeft: Math.round(r.left * 10) / 10,
                modalRight: Math.round(r.right * 10) / 10,
                doc: sw(d.documentElement)
              };
              // 「✓ 名前 日時」が名前（.transfer-pair）の下の行にあるか
              var by = ov.querySelector('.transfer-row.done .transfer-by');
              var pair = by ? by.parentNode.querySelector('.transfer-pair') : null;
              out.byBelow = !!(by && pair &&
                by.getBoundingClientRect().top >= pair.getBoundingClientRect().bottom - 1);
              // inline のときは clientWidth が 0 になるので、描画幅（getBoundingClientRect）で出す
              var rw = function (el) { return el ? Math.round(el.getBoundingClientRect().width) : -1; };
              out.pairW = rw(pair);
              out.byW = rw(by);
              f.remove();
              resolve(out);
            };
            document.body.appendChild(f);
          });
        }
        function desc(m) {
          return m.width + 'px: modal ' + m.modal.sw + '/' + m.modal.cw +
            ' past ' + m.past.sw + '/' + m.past.cw +
            ' row ' + m.row.sw + '/' + m.row.cw +
            ' names ' + m.names.sw + '/' + m.names.cw +
            ' modalRect ' + m.modalLeft + '..' + m.modalRight + ' (vw ' + m.vw + ')' +
            ' doc ' + m.doc.sw + '/' + m.doc.cw +
            ' pairW ' + m.pairW + ' byW ' + m.byW +
            ' byBelow ' + m.byBelow;
        }
        function fits(m) {
          return m.modal.cw > 0 && m.modal.sw <= m.modal.cw &&
            m.past.sw <= m.past.cw && m.row.sw <= m.row.cw &&
            m.modalRight <= m.vw;
        }

        return measure(375).then(function (m) {
          results.push('info 過去の清算の幅 ' + desc(m));
          check('スマホ幅 375px: 過去の清算の行がはみ出さない（モーダル・.past-settlement・.transfer-row）',
            fits(m), desc(m));
          check('スマホ幅 375px: 「✓ 名前 日時」は名前の下の行に出る', m.byBelow, desc(m));
          return measure(1024);
        }).then(function (m) {
          results.push('info 過去の清算の幅 ' + desc(m));
          check('PC 幅 1024px: 過去の清算の行がはみ出さない', fits(m), desc(m));
          check('PC 幅 1024px: 「✓ 名前 日時」は今までどおり名前と同じ行', !m.byBelow, desc(m));
          root.closeModal('settlementModal');
          return wait(40);
        });
      })

      .then(function () {
        root.doLogout();
        return wait(120);
      })
      .then(function () {
        check('ログアウトでログイン画面に戻る（2 回目）',"""))


def main():
    with io.open(DRIVER, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "工事4d-B" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    errors = []
    for before, _ in EDITS:
        n = src.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for before, after in EDITS:
        out = out.replace(fix(before), fix(after), 1)

    with io.open(DRIVER, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + DRIVER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
