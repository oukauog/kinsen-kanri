# -*- coding: utf-8 -*-
"""
工事2: index.html に
  ① js/migrate.js の読み込み
  ② オフラインの細いバナー
  ③ 取り込むグループの選択モーダル
  ④ 取り込み結果モーダル
を足す。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_index_migrate.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")

REPLACEMENTS = []

# ① 読み込み順: calc の後（migrate は calc を使う）、store の前
REPLACEMENTS.append((
    "js/migrate.js の読み込みを追加",
    """<script src="js/calc.js"></script>
<script src="js/store.js"></script>""",
    """<script src="js/calc.js"></script>
<script src="js/migrate.js"></script>
<script src="js/store.js"></script>"""))

# ② オフラインバナー（ヘッダの直後。アプリ画面でもログイン画面でも同じ位置に出る）
REPLACEMENTS.append((
    "オフラインのバナーを追加",
    """<div class="sidebar-backdrop" onclick="toggleSidebar()"></div>""",
    """<div class="offline-banner" id="offlineBanner" hidden>オフラインです。変更は再接続後に送信されます</div>

<div class="sidebar-backdrop" onclick="toggleSidebar()"></div>"""))

# ③④ モーダル 2 つ（「コードで参加」モーダルの後ろに置く）
REPLACEMENTS.append((
    "取り込みの選択・結果モーダルを追加",
    """<!-- Firebase SDK（compat 版）-->""",
    """<!-- Modal: 取り込むグループの選択（旧バージョンからの移行） -->
<div class="modal-overlay" id="migrateModal">
  <div class="modal">
    <div class="modal-title">&#x1F4E6; 旧バージョンのデータを取り込む</div>
    <div id="migrateContent"></div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="cancelMigrate()">キャンセル</button>
      <button class="btn btn-primary" id="migrateConfirmBtn" onclick="confirmMigrate()">取り込む</button>
    </div>
  </div>
</div>

<!-- Modal: 取り込み結果 -->
<div class="modal-overlay" id="migrateResultModal">
  <div class="modal">
    <div class="modal-title">&#x2705; 取り込みが終わりました</div>
    <div id="migrateResultContent"></div>
    <div class="modal-footer">
      <button class="btn btn-primary" onclick="closeMigrateResult()">閉じる</button>
    </div>
  </div>
</div>

<!-- Firebase SDK（compat 版）-->"""))


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

    # 開閉タグの整合
    assert out.count("<div") == out.count("</div>"), \
        "div の開閉が合わない: %d / %d" % (out.count("<div"), out.count("</div>"))
    assert out.count("<script") == out.count("</script>")
    assert "</body>" in out and "</html>" in out

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: %s（div %d 組、script %d 組）"
          % (TARGET, out.count("<div"), out.count("<script")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
