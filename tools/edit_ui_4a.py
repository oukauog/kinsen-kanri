# -*- coding: utf-8 -*-
"""
工事4a: js/ui.js に
  ① CSV 出力（ボタンの復元、v1 のモーダル再利用、ダウンロード）
  ② アプリ内ブラウザの案内と URL コピー
を足す。取込（xlsx/CSV）は工事4b なので触らない。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_4a.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

REPLACEMENTS = []

# ① Csv / Env を掴む
REPLACEMENTS.append((
    "Csv と Env を参照する",
    """  var Migrate = root.Migrate;
  var Settle = root.Settle;""",
    """  var Migrate = root.Migrate;
  var Settle = root.Settle;
  var Csv = root.Csv;
  var Env = root.Env;"""))

# ② グループ画面のボタン列に CSV 出力を戻す
REPLACEMENTS.append((
    "CSV 出力ボタンを戻す",
    """          '<button class="btn btn-secondary" onclick="openSettlement()">清算</button>' +
          '<button class="btn btn-secondary" onclick="openSettings()">設定</button>' +""",
    """          '<button class="btn btn-secondary" onclick="openSettlement()">清算</button>' +
          '<button class="btn btn-secondary" onclick="openExportModal()">CSV出力</button>' +
          '<button class="btn btn-secondary" onclick="openSettings()">設定</button>' +"""))

# ③ CSV 出力一式（グループ設定の節の手前に置く）
REPLACEMENTS.append((
    "CSV 出力を追加",
    """  // ---- グループ設定 ---------------------------------------------------""",
    """  // ---- CSV 出力（工事4a）----------------------------------------------

  /** v1 と同じやり方でファイルを落とす（Blob + a[download]） */
  function downloadCsv(text, filename) {
    var blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function groupNameForFile() {
    var n = currentGroup && currentGroup.meta && currentGroup.meta.name
      ? currentGroup.meta.name : 'グループ';
    return Csv.safeFileName(n);
  }

  /** 支払い一覧の CSV（本文とファイル名）。テストから中身を見られるように分けてある */
  function buildPaymentsCsv() {
    if (!currentGroup) return null;
    return {
      text: Csv.paymentsCsv(currentGroup, currentGroup.payments || {},
        currentGroup.settlements || {}),
      name: groupNameForFile() + '_支払い_' + Csv.stamp() + '.csv'
    };
  }

  /** 残高の CSV。いま画面に出ている表示（未清算のみ / 累計）で出す */
  function buildBalancesCsv() {
    if (!currentGroup) return null;
    return {
      text: Csv.balancesCsv(currentGroup, currentGroup.payments || {}, balanceMode),
      name: groupNameForFile() + '_残高_' + Csv.stamp() + '.csv'
    };
  }

  function openExportModal() {
    if (!currentGroup) return;
    $('exportBtns').innerHTML =
      '<button class="export-btn-row" onclick="exportPaymentsCsv()">' +
        '<span class="export-btn-icon">&#x1F4CB;</span>' +
        '<div><span class="export-btn-label">支払い一覧（CSV）</span>' +
        '<span class="export-btn-desc">日付・メモ・支払った人・金額・割り勘対象・1人あたり・清算状態</span>' +
        '</div></button>' +
      '<button class="export-btn-row" onclick="exportBalancesCsv()">' +
        '<span class="export-btn-icon">&#x1F4CA;</span>' +
        '<div><span class="export-btn-label">残高（CSV）</span>' +
        '<span class="export-btn-desc">メンバーごとの払った合計・負担分・残高</span>' +
        '</div></button>' +
      '<div class="export-note">残高 CSV は、いまの表示（<strong>' +
      (balanceMode === 'all' ? '累計' : '未清算のみ') + '</strong>）で出します。' +
      '切り替えたいときは、いったん閉じて残高の右上で切り替えてください。</div>';
    openModal('exportModal');
  }

  function exportPaymentsCsv() {
    var r = buildPaymentsCsv();
    if (!r) return null;
    downloadCsv(r.text, r.name);
    closeModal('exportModal');
    toast('支払い一覧を書き出しました: ' + r.name);
    return r;
  }

  function exportBalancesCsv() {
    var r = buildBalancesCsv();
    if (!r) return null;
    downloadCsv(r.text, r.name);
    closeModal('exportModal');
    toast('残高を書き出しました: ' + r.name);
    return r;
  }

  // ---- アプリ内ブラウザの案内（工事4a、§5.1）--------------------------

  /** LINE や Discord の中のブラウザなら案内を出す。ログインボタンは残したまま */
  function checkInAppBrowser() {
    var box = $('inAppNotice');
    if (!box || !Env) return false;
    var inApp = Env.isInAppBrowser(navigator.userAgent);
    box.hidden = !inApp;
    return inApp;
  }

  /** 開いている URL をコピー。できない環境では画面に出して手で選べるようにする */
  function copyPageUrl() {
    var url = location.href;
    var show = function () {
      var el = $('inAppUrl');
      if (el) { el.textContent = url; el.hidden = false; }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        var btn = $('btnCopyUrl');
        if (btn) {
          btn.textContent = 'コピーしました！';
          setTimeout(function () { btn.textContent = 'URL をコピー'; }, 1800);
        }
      }, show);
    } else {
      show();
    }
  }

  // ---- グループ設定 ---------------------------------------------------"""))

# ④ 起動時にアプリ内ブラウザを判定する
REPLACEMENTS.append((
    "起動時にアプリ内ブラウザを判定する",
    """    document.querySelectorAll('.modal-overlay').forEach(function (ov) {""",
    """    checkInAppBrowser();

    document.querySelectorAll('.modal-overlay').forEach(function (ov) {"""))

# ⑤ Firebase が読めなかったときも案内を出す（ログイン画面を出す枝）
REPLACEMENTS.append((
    "Firebase が読めないときも案内を出す",
    """    if (!root.KKFirebase || !root.KKFirebase.ready) {
      hideBoot();
      $('loginScreen').hidden = false;""",
    """    if (!root.KKFirebase || !root.KKFirebase.ready) {
      hideBoot();
      checkInAppBrowser();
      $('loginScreen').hidden = false;"""))

# ⑥ global に出す
REPLACEMENTS.append((
    "CSV と案内を global に出す",
    """  root.openSettings = openSettings;""",
    """  root.openExportModal = openExportModal;
  root.exportPaymentsCsv = exportPaymentsCsv;
  root.exportBalancesCsv = exportBalancesCsv;
  root.buildPaymentsCsv = buildPaymentsCsv;
  root.buildBalancesCsv = buildBalancesCsv;
  root.copyPageUrl = copyPageUrl;
  root.checkInAppBrowser = checkInAppBrowser;
  root.openSettings = openSettings;"""))


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors, plan = [], []
    for label, before, after in REPLACEMENTS:
        b = fix(before)
        n = src.count(b)
        if n != 1:
            errors.append("%s: 一致 %d 件（1 件であるべき）" % (label, n))
        plan.append((label, b, fix(after)))

    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for label, b, a in plan:
        out = out.replace(b, a, 1)
        print("置換しました: " + label)

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
