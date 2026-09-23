# -*- coding: utf-8 -*-
"""
工事4a: 画面の通し確認に CSV 出力とアプリ内ブラウザの案内を足す。

  ・CSV モーダルが開く / 2 つのボタンと残高モードの注記が出る
  ・支払い CSV の中身（先頭が BOM、ヘッダ、1 行目）
  ・残高 CSV のモード表記（未清算のみ / 累計）
  ・アプリ内ブラウザの UA で案内が出る、通常の UA では出ない

ダウンロード自体はヘッドレスでは確かめられないので、
中身を組み立てるところ（buildPaymentsCsv / buildBalancesCsv）を見る。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_4a.py
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

AFTER = """      // ══ 工事4a: CSV 出力 ══
      .then(function () {
        root.openExportModal();
        check('CSV 出力モーダルが開く', isOpen('exportModal'));
        check('CSV のボタンが 2 つ出る',
          $('exportBtns').querySelectorAll('.export-btn-row').length === 2);
        check('残高 CSV は今の表示モードで出す旨が出る',
          $('exportBtns').textContent.indexOf('未清算のみ') >= 0,
          $('exportBtns').textContent);
        root.closeModal('exportModal');

        var p = root.buildPaymentsCsv();
        check('支払い CSV の先頭が BOM', p.text.charCodeAt(0) === 0xFEFF);
        var rows = p.text.slice(1).replace(/\\r\\n$/, '').split('\\r\\n');
        check('支払い CSV のヘッダが仕様どおり',
          rows[0] === '日付,メモ,支払った人,金額,割り勘対象,1人あたり,清算状態', rows[0]);
        check('支払い CSV の 1 行目が画面の先頭と同じ支払い',
          rows[1].indexOf('テスト2回目の支払い') >= 0 && rows[1].indexOf('1200') >= 0, rows[1]);
        check('支払い CSV に清算状態が入る',
          rows[1].split(',').pop().indexOf('清算済み') === 0, rows[1]);
        check('支払い CSV のファイル名にグループ名と日付が入る',
          p.name.indexOf('テスト清算_支払い_') === 0 && /\\d{8}\\.csv$/.test(p.name), p.name);

        var b = root.buildBalancesCsv();
        var brows = b.text.slice(1).replace(/\\r\\n$/, '').split('\\r\\n');
        check('残高 CSV の 1 行目が未清算のみのコメント行',
          brows[0] === '# 残高（未清算のみ）', brows[0]);
        check('残高 CSV のヘッダが仕様どおり',
          brows[1] === 'メンバー,払った合計,負担分,残高', brows[1]);
        check('残高 CSV のファイル名が残高になっている',
          b.name.indexOf('テスト清算_残高_') === 0, b.name);

        root.setBalanceMode('all');
        return wait(40);
      })
      .then(function () {
        var b2 = root.buildBalancesCsv();
        check('累計に切り替えると残高 CSV のコメント行も累計になる',
          b2.text.slice(1).split('\\r\\n')[0] === '# 残高（累計）',
          b2.text.slice(1).split('\\r\\n')[0]);
        root.openExportModal();
        check('CSV モーダルの注記も累計になる',
          $('exportBtns').textContent.indexOf('累計') >= 0);
        root.closeModal('exportModal');
        root.setBalanceMode('unsettled');
        return wait(40);
      })

      // ══ 工事4a: アプリ内ブラウザの案内 ══
      .then(function () {
        check('通常のブラウザでは案内が出ていない', $('inAppNotice').hidden === true);
        check('判定の関数が UA を見ている（LINE の UA なら true）',
          root.Env.isInAppBrowser('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Line/14.5.0') === true);
        check('普通の Safari なら false',
          root.Env.isInAppBrowser('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1') === false);

        // UA を差し替えて、起動時の判定が案内を出すことを確かめる
        var realUA = navigator.userAgent;
        try {
          Object.defineProperty(navigator, 'userAgent', {
            value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) ' +
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Line/14.5.0',
            configurable: true
          });
          root.checkInAppBrowser();
          check('アプリ内ブラウザの UA なら案内が出る', $('inAppNotice').hidden === false);
          check('案内に Safari / Chrome で開く説明が出る',
            $('inAppNotice').textContent.indexOf('Safari で開く') >= 0);
          check('URL をコピーするボタンがある', !!$('btnCopyUrl'));
          check('案内が出てもログインボタンは残る（誤判定に備える）',
            !!$('btnLogin') && $('btnLogin').offsetParent !== null);
          Object.defineProperty(navigator, 'userAgent', { value: realUA, configurable: true });
          root.checkInAppBrowser();
          check('通常の UA に戻すと案内が消える', $('inAppNotice').hidden === true);
        } catch (e) {
          check('UA を差し替えて案内の出し分けを確かめる', false, e.message);
        }
        return wait(20);
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

    if "buildPaymentsCsv" in src:
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
