# -*- coding: utf-8 -*-
"""
工事3: css/v2.css に、金額確認中・清算済み・清算モーダルのスタイルを足す。
末尾のモバイル用 @media の直前に差し込み、モバイル用の追記も足す。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_css_settle.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "css", "v2.css")

ANCHOR = """/* ── モバイル ───────────────────────────────── */
@media (max-width: 640px) {"""

ADDITION = """/* ── 金額確認中 / 清算済み（工事3）──────────────── */
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 0.85rem;
  color: var(--gray-700);
  cursor: pointer;
  user-select: none;
}
.check-row input { width: 16px; height: 16px; flex-shrink: 0; cursor: pointer; }
.check-hint { font-size: 0.75rem; color: var(--gray-500); margin-top: 4px; line-height: 1.5; }

.payment-item.pending { background: #fffbeb; border-color: #fde68a; }
.payment-item.pending .payment-total { color: #b45309; font-size: 0.9rem; }
.payment-item.settled { background: var(--gray-50); color: var(--gray-500); }
.payment-item.settled .payment-payer,
.payment-item.settled .payment-total { color: var(--gray-500); }
.payment-item.settled .btn-edit,
.payment-item.settled .btn-delete { opacity: 0.35; cursor: not-allowed; }
.pay-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  margin-left: 6px;
  vertical-align: 1px;
  white-space: nowrap;
}
.pay-badge.settled { background: var(--gray-200); color: var(--gray-500); }
.pay-badge.pending { background: #fde68a; color: #92400e; }

/* ── 残高の見出し（未清算 / 累計の切替）────────── */
.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.section-head .section-title { margin-bottom: 0; }
.balance-mode {
  margin-left: auto;
  display: flex;
  border: 1px solid var(--gray-300);
  border-radius: 999px;
  overflow: hidden;
  background: white;
  flex-shrink: 0;
}
.balance-mode button {
  border: none;
  background: none;
  font-family: inherit;
  font-size: 0.72rem;
  padding: 5px 11px;
  cursor: pointer;
  color: var(--gray-500);
  white-space: nowrap;
}
.balance-mode button.active { background: var(--primary); color: white; font-weight: 600; }
.pending-note {
  font-size: 0.72rem;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 999px;
  padding: 3px 10px;
  white-space: nowrap;
}

/* ── 清算モーダル ──────────────────────────── */
.modal-wide { max-width: 560px; }
.settle-section { margin-bottom: 22px; }
.settle-section:last-child { margin-bottom: 0; }
.settle-head {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--gray-500);
  letter-spacing: 0.06em;
  margin-bottom: 10px;
}
.settle-sub { font-size: 0.78rem; color: var(--gray-500); margin-top: 8px; line-height: 1.6; }
.settle-warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 0.82rem;
  line-height: 1.6;
  margin-bottom: 14px;
}
.settle-warn ul { margin: 8px 0 0 18px; padding: 0; }
.settle-warn li { margin-top: 3px; }
.settle-confirm-row { display: flex; justify-content: flex-end; margin-top: 14px; }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }

.past-settlement {
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 13px 15px;
  margin-bottom: 10px;
  background: white;
}
.past-settlement.old { background: var(--gray-50); }
.past-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 9px; }
.past-date { font-size: 0.85rem; font-weight: 600; }
.past-count { font-size: 0.75rem; color: var(--gray-500); }
.past-done-badge {
  font-size: 0.68rem;
  font-weight: 700;
  background: var(--green-light);
  color: #15803d;
  border-radius: 999px;
  padding: 2px 9px;
}
.transfer-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 0;
  font-size: 0.85rem;
  border-top: 1px solid var(--gray-100);
}
.transfer-row input { width: 17px; height: 17px; flex-shrink: 0; cursor: pointer; }
.transfer-row.done .transfer-names { text-decoration: line-through; color: var(--gray-500); }
.transfer-names { flex: 1; min-width: 0; }
.transfer-amount { font-weight: 700; flex-shrink: 0; }
.past-foot { margin-top: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.past-note { font-size: 0.72rem; color: var(--gray-500); }

"""

MOBILE_ANCHOR = """  .login-card { padding: 24px 18px; }
}"""

MOBILE_ADD = """  .login-card { padding: 24px 18px; }

  /* 工事3 */
  .section-head { gap: 6px; }
  .balance-mode button { font-size: 0.68rem; padding: 4px 9px; }
  .pending-note { font-size: 0.68rem; padding: 2px 8px; }
  .pay-badge { font-size: 0.6rem; padding: 1px 6px; }
  .transfer-row { font-size: 0.8rem; gap: 7px; }
  .past-settlement { padding: 11px 12px; }
}"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if ".payment-item.pending" in src:
        print("すでに適用済みです。何もしません。")
        return 0

    pairs = [
        ("清算まわりのスタイルを追加", fix(ANCHOR), fix(ADDITION) + fix(ANCHOR)),
        ("モバイル用の調整を追加", fix(MOBILE_ANCHOR), fix(MOBILE_ADD)),
    ]
    for label, before, after in pairs:
        if src.count(before) != 1:
            print("中止しました（%s: 一致 %d 件）。ファイルは変更していません。"
                  % (label, src.count(before)))
            return 1

    out = src
    for label, before, after in pairs:
        out = out.replace(before, after, 1)
        print("置換しました: " + label)

    if out.count("{") != out.count("}"):
        print("中止しました（波括弧の数が合いません）")
        return 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
