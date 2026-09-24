# -*- coding: utf-8 -*-
"""
工事4b-C: 「過去の清算」を新しい順に 5 件までにし、
6 件以上あるときは「もっと見る（残り N 件）」で全件に切り替えられるようにする。

  ・新しい順に並んでいるので、折りたたんでも最新の清算（取り消せる 1 件）は必ず出る
  ・展開状態は保存しない（モーダルを開き直す・グループを変えると 5 件に戻る）
  ・最新 1 件のみ取消可、送金チェックの他端末反映はそのまま

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_pastlimit_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

REPLACEMENTS = []

# ① 状態（保存しない）
REPLACEMENTS.append((
    "過去の清算の展開状態を持つ",
    """  var newMembers = [];        // 新規グループ作成モーダルの作業用""",
    """  var showAllSettlements = false;   // 過去の清算を全件出すか（保存しない。工事4b）
  var PAST_LIMIT = 5;              // 折りたたみ時に出す件数
  var newMembers = [];        // 新規グループ作成モーダルの作業用"""))

# ② 表示を 5 件までに
REPLACEMENTS.append((
    "過去の清算を 5 件までにする",
    """    if (past.length === 0) {
      html += '<div class="settle-sub">まだ清算の記録はありません。</div>';
    } else {
      html += past.map(function (s) {""",
    """    if (past.length === 0) {
      html += '<div class="settle-sub">まだ清算の記録はありません。</div>';
    } else {
      // 新しい順なので、折りたたんでも最新の清算（取り消せる 1 件）は必ず出る
      var shown = showAllSettlements ? past : past.slice(0, PAST_LIMIT);
      var rest = past.length - shown.length;
      html += shown.map(function (s) {"""))

# ③ もっと見るボタン
REPLACEMENTS.append((
    "もっと見るボタンを足す",
    """          '</div></div>';
      }).join('');
    }
    html += '</div>';

    $('settlementContent').innerHTML = html;""",
    """          '</div></div>';
      }).join('');
      if (rest > 0) {
        html += '<button class="btn btn-secondary btn-sm past-more" id="pastMoreBtn" ' +
          'onclick="showAllPastSettlements()">もっと見る（残り ' + rest + ' 件）</button>';
      }
    }
    html += '</div>';

    $('settlementContent').innerHTML = html;"""))

# ④ 展開の操作
REPLACEMENTS.append((
    "もっと見るの操作を足す",
    """  /** 「この内容で清算する」 */""",
    """  /** 「もっと見る」: 過去の清算を全件出す（保存しないので開き直せば戻る） */
  function showAllPastSettlements() {
    showAllSettlements = true;
    renderSettlement();
  }

  /** 「この内容で清算する」 */"""))

# ⑤ 開くたびに折りたたみから
REPLACEMENTS.append((
    "清算モーダルを開くときは折りたたみから始める",
    """  function openSettlement() {
    if (!currentGroup) return;
    renderSettlement();
    openModal('settlementModal');
  }""",
    """  function openSettlement() {
    if (!currentGroup) return;
    showAllSettlements = false;   // 開くたびに 5 件から（工事4b）
    renderSettlement();
    openModal('settlementModal');
  }"""))

# ⑥ グループを変えたら戻す
REPLACEMENTS.append((
    "グループを切り替えたら折りたたみに戻す",
    """    currentCode = code;
    currentGroup = null;
    seenPaymentAt = null;""",
    """    currentCode = code;
    currentGroup = null;
    seenPaymentAt = null;
    showAllSettlements = false;   // グループを変えたら過去の清算は 5 件に戻す"""))

# ⑦ global
REPLACEMENTS.append((
    "もっと見るを global に出す",
    """  root.doUndoSettlement = doUndoSettlement;""",
    """  root.doUndoSettlement = doUndoSettlement;
  root.showAllPastSettlements = showAllPastSettlements;"""))


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
