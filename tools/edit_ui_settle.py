# -*- coding: utf-8 -*-
"""
工事3: js/ui.js に
  ① 金額確認中（入力モーダルのチェック、履歴の薄黄色表示）
  ② 清算済みのグレー表示とボタン無効化
  ③ 残高カードの「未清算のみ / 累計」切替（kk_v2_balanceMode に保存）
  ④ 清算モーダルの作り直し（今回の清算 + 過去の清算・送金チェック・取り消し）
を足す。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_settle.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

REPLACEMENTS = []

# ① Settle を掴む・状態を足す
REPLACEMENTS.append((
    "Settle を参照し、残高の表示モードを持つ",
    """  var Migrate = root.Migrate;

  var LS_LAST_GROUP = 'kk_v2_lastGroup';   // v2 が使う localStorage は kk_v2_* のみ""",
    """  var Migrate = root.Migrate;
  var Settle = root.Settle;

  var LS_LAST_GROUP = 'kk_v2_lastGroup';   // v2 が使う localStorage は kk_v2_* のみ
  var LS_BALANCE_MODE = 'kk_v2_balanceMode';

  // 残高カードの表示: 'unsettled'（未清算のみ。既定） / 'all'（累計）
  var balanceMode = (function () {
    try {
      return localStorage.getItem(LS_BALANCE_MODE) === 'all' ? 'all' : 'unsettled';
    } catch (e) { return 'unsettled'; }
  })();"""))

# ② 日時の表示と清算の取り出しを足す
REPLACEMENTS.append((
    "日時の表示と清算レコードの取り出しを足す",
    """  function memberName(members, mid) {
    for (var i = 0; i < members.length; i++) if (members[i].id === mid) return members[i].name;
    return '?';
  }""",
    """  function memberName(members, mid) {
    for (var i = 0; i < members.length; i++) if (members[i].id === mid) return members[i].name;
    return '?';
  }

  /** ミリ秒 → 「2026/09/24 18:30」 */
  function dateTime(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '/' + p(d.getMonth() + 1) + '/' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** 開いているグループの清算レコード（無ければ {}） */
  function settlementsOf(group) {
    return (group && group.settlements) ? group.settlements : {};
  }"""))

# ③ renderMain: 残高の絞り込み・切替・確認中の注記
REPLACEMENTS.append((
    "残高を未清算/累計で切り替える",
    """    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    var bal = Calc.calcBalances(members, pays);
    var groupName = currentGroup.meta && currentGroup.meta.name ? currentGroup.meta.name : '(名称未設定)';""",
    """    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    // 残高は既定で「未清算のみ」。確認中（pending）はどちらのモードでも外す（§5.3.1、§5.4）
    var pendings = Settle.pickPending(pays);
    var balSource = balanceMode === 'all'
      ? Settle.pickAllButPending(pays)
      : Settle.pickUnsettled(pays);
    var bal = Calc.calcBalances(members, balSource);
    var groupName = currentGroup.meta && currentGroup.meta.name ? currentGroup.meta.name : '(名称未設定)';"""))

# ④ 履歴の行: 確認中・清算済み
REPLACEMENTS.append((
    "履歴の行に確認中・清算済みの表示を足す",
    """        return '<div class="payment-item' + (fresh[p.id] ? ' flash' : '') + '">' +
          '<div class="payment-date">' + esc(p.date) + '</div>' +
          '<div class="payment-info">' +
            '<div class="payment-payer">' + esc(p.memo || '支払い') + '</div>' +
            '<div class="payment-memo">' + esc(memberName(members, p.payerId)) + ' が支払い</div>' +
            '<div class="payment-participants">' + esc(partNames) + '</div>' +
          '</div>' +
          '<div class="payment-amounts"><div class="payment-total">' + money(p.amount) + '</div>' +
          '<div class="payment-per">1人 ' + money(per) + '</div></div>' +
          '<button class="btn-edit" onclick="openEditPayModal(\\'' + p.id + '\\')" title="編集">&#x270F;</button>' +
          '<button class="btn-delete" onclick="deletePay(\\'' + p.id + '\\')" title="削除">&#x2715;</button>' +
          '</div>';""",
    """        var isPending = p.pending === true;
        var isSettled = p.settlementId != null;
        var cls = 'payment-item' + (fresh[p.id] ? ' flash' : '') +
          (isPending ? ' pending' : '') + (isSettled ? ' settled' : '');
        var badge = isSettled ? '<span class="pay-badge settled">清算済み</span>'
          : isPending ? '<span class="pay-badge pending">確認中</span>' : '';
        var amountHTML = isPending
          ? '<div class="payment-total">確認中</div>'
          : '<div class="payment-total">' + money(p.amount) + '</div>' +
            '<div class="payment-per">1人 ' + money(per) + '</div>';
        // 清算済みは編集・削除できない（データ層でも止めている）
        var editBtn = isSettled
          ? '<button class="btn-edit" onclick="lockedNotice()" title="清算済み">&#x270F;</button>'
          : '<button class="btn-edit" onclick="openEditPayModal(\\'' + p.id + '\\')" title="編集">&#x270F;</button>';
        var delBtn = isSettled
          ? '<button class="btn-delete" onclick="lockedNotice()" title="清算済み">&#x2715;</button>'
          : '<button class="btn-delete" onclick="deletePay(\\'' + p.id + '\\')" title="削除">&#x2715;</button>';
        return '<div class="' + cls + '">' +
          '<div class="payment-date">' + esc(p.date) + '</div>' +
          '<div class="payment-info">' +
            '<div class="payment-payer">' + esc(p.memo || '支払い') + badge + '</div>' +
            '<div class="payment-memo">' + esc(memberName(members, p.payerId)) + ' が支払い</div>' +
            '<div class="payment-participants">' + esc(partNames) + '</div>' +
          '</div>' +
          '<div class="payment-amounts">' + amountHTML + '</div>' +
          editBtn + delBtn +
          '</div>';"""))

# ⑤ 残高の見出しに切替トグルと確認中の注記
REPLACEMENTS.append((
    "残高の見出しに切替と確認中の注記を出す",
    """      '<div class="section-title">残高 — マイナスが大きい人が次の支払い候補</div>' +
      '<div class="balance-grid">' + balHTML + '</div>' +
      '<div class="section-title">支払い履歴</div>' + paysHTML;""",
    """      '<div class="section-head">' +
        '<div class="section-title">残高 — ' +
        (balanceMode === 'all' ? '累計' : '未清算分') + '</div>' +
        (pendings.length
          ? '<span class="pending-note">金額確認中 ' + pendings.length +
            ' 件（計算に含まれていません）</span>' : '') +
        '<div class="balance-mode">' +
          '<button class="' + (balanceMode === 'unsettled' ? 'active' : '') +
          '" onclick="setBalanceMode(\\'unsettled\\')">未清算のみ</button>' +
          '<button class="' + (balanceMode === 'all' ? 'active' : '') +
          '" onclick="setBalanceMode(\\'all\\')">累計を見る</button>' +
        '</div>' +
      '</div>' +
      '<div class="balance-grid">' + balHTML + '</div>' +
      '<div class="section-title">支払い履歴</div>' + paysHTML;"""))

# ⑥ 描画のたびに、開いている清算モーダルも作り直す（他端末の変更を即反映）
REPLACEMENTS.append((
    "清算モーダルが開いていれば一緒に描き直す",
    """  function render() { renderSidebar(); renderMain(); }""",
    """  function render() {
    renderSidebar();
    renderMain();
    // 清算モーダルを開いたまま他端末の変更が届いたら、その場で描き直す
    var sm = $('settlementModal');
    if (sm && sm.classList.contains('open') && currentGroup) renderSettlement();
  }

  function setBalanceMode(mode) {
    balanceMode = (mode === 'all') ? 'all' : 'unsettled';
    try { localStorage.setItem(LS_BALANCE_MODE, balanceMode); } catch (e) { /* noop */ }
    renderMain();
  }

  function lockedNotice() {
    toast('清算済みの支払いは編集できません。先に清算を取り消してください', 'error');
  }"""))

# ⑦ 支払いモーダル: 確認中の読み書き
REPLACEMENTS.append((
    "支払いモーダルで金額確認中を扱う",
    """    $('payDate').value = pay ? pay.date : today();
    $('payMemo').value = pay ? (pay.memo || '') : '';
    $('payAmount').value = pay ? pay.amount : '';""",
    """    if (pay && pay.settlementId != null) { lockedNotice(); return; }
    $('payDate').value = pay ? pay.date : today();
    $('payMemo').value = pay ? (pay.memo || '') : '';
    $('payPending').checked = !!(pay && pay.pending === true);
    $('payAmount').value = (pay && pay.pending !== true) ? pay.amount : '';
    onPendingToggle();"""))

REPLACEMENTS.append((
    "金額確認中のチェックで金額欄の見え方を変える",
    """  function openEditPayModal(id) { openPaymentModal(id); }
  function toggleChip(el) { el.classList.toggle('selected'); }""",
    """  function openEditPayModal(id) { openPaymentModal(id); }
  function toggleChip(el) { el.classList.toggle('selected'); }

  /** 「金額確認中」の切替。☑ のときは金額が空でも登録できる（§5.3.1）*/
  function onPendingToggle() {
    var pending = $('payPending').checked;
    var amount = $('payAmount');
    amount.placeholder = pending ? 'あとで入力' : '0';
    $('payPendingHint').textContent = pending
      ? '金額が決まったら、この支払いを編集してチェックを外してください'
      : '確認中の支払いは残高と清算の計算に入りません';
  }"""))

# ⑧ 登録時の検証と pending の受け渡し
REPLACEMENTS.append((
    "登録時に金額確認中を受け渡す",
    """    var amount = parseFloat($('payAmount').value);
    if (!date) { alert('日付を入力してください'); return; }
    if (!amount || amount <= 0) { alert('金額を入力してください'); return; }""",
    """    var pending = $('payPending').checked;
    var amount = parseFloat($('payAmount').value);
    if (!date) { alert('日付を入力してください'); return; }
    if (pending) {
      amount = 0;                      // 金額確認中は 0 で持つ（計算からは外れる）
    } else if (!amount || amount <= 0) {
      alert('金額を入力してください'); return;
    }"""))

REPLACEMENTS.append((
    "保存する中身に pending を足す",
    """    var payload = { date: date, memo: memo, payerId: payerId, amount: amount, participants: participants };""",
    """    var payload = {
      date: date, memo: memo, payerId: payerId, amount: amount,
      participants: participants, pending: pending
    };"""))

# ⑨ 清算モーダルの作り直し
REPLACEMENTS.append((
    "清算モーダルを清算レコード対応に作り直す",
    """  // ---- 清算（工事1 では送金リストの表示のみ） --------------------------

  function openSettlement() {
    if (!currentGroup) return;
    var members = memberList(currentGroup);
    var txns = Calc.calcSettlement(members, paymentList(currentGroup));
    var el = $('settlementContent');
    if (txns.length === 0) {
      el.innerHTML = '<div class="settlement-empty">🎉 全員の貸し借りはありません！</div>';
    } else {
      el.innerHTML = '<div class="settlement-list">' + txns.map(function (t) {
        return '<div class="settlement-item"><span class="settlement-from">' + esc(t.from) + '</span>' +
          '<span class="settlement-arrow">&#x2192;</span>' +
          '<span class="settlement-to">' + esc(t.to) + '</span>' +
          '<span class="settlement-amount">' + money(t.amount) + '</span></div>';
      }).join('') + '</div>' +
      '<div class="settlement-note">※ この清算はまだ記録されません（清算の記録は工事3 で追加）</div>';
    }
    openModal('settlementModal');
  }""",
    """  // ---- 清算（工事3: 記録・チェック・取り消し）--------------------------

  function openSettlement() {
    if (!currentGroup) return;
    renderSettlement();
    openModal('settlementModal');
  }

  /** 清算モーダルの中身を作る（開いている間、データが変わるたびに呼ばれる）*/
  function renderSettlement() {
    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    var pendings = Settle.pickPending(pays);
    var targets = Settle.pickUnsettled(pays);
    var me = Auth.user();
    var draft = Settle.buildSettlement(members, pays, {
      uid: me ? me.uid : '', now: Date.now()
    });

    // ── 今回の清算 ──
    var html = '<div class="settle-section"><div class="settle-head">今回の清算</div>';

    if (pendings.length) {
      html += '<div class="settle-warn">金額確認中の支払いが ' + pendings.length +
        ' 件あります。金額を確定してから清算してください。<ul>' +
        pendings.map(function (p) {
          return '<li>' + esc(p.date) + ' ' + esc(p.memo || '(メモなし)') + '</li>';
        }).join('') + '</ul></div>';
    }

    if (!draft) {
      html += '<div class="settlement-empty">' +
        (targets.length === 0 ? '未清算の支払いはありません。' : '🎉 未清算の貸し借りはありません！') +
        '</div>';
    } else {
      html += '<div class="settlement-list">' +
        Settle.transferList(draft).map(function (t) {
          return '<div class="settlement-item">' +
            '<span class="settlement-from">' + esc(t.fromName) + '</span>' +
            '<span class="settlement-arrow">&#x2192;</span>' +
            '<span class="settlement-to">' + esc(t.toName) + '</span>' +
            '<span class="settlement-amount">' + money(t.amount) + '</span></div>';
        }).join('') + '</div>' +
        '<div class="settle-sub">対象の支払い ' + targets.length + ' 件 ・ 送金 ' +
        Settle.transferList(draft).length + ' 本</div>' +
        '<div class="settle-confirm-row">' +
        '<button class="btn btn-primary" id="settleConfirmBtn" onclick="doConfirmSettlement()"' +
        (pendings.length ? ' disabled title="金額確認中の支払いがあります"' : '') +
        '>この内容で清算する</button></div>';
    }
    html += '</div>';

    // ── 過去の清算 ──
    var past = Settle.listSettlements(settlementsOf(currentGroup));
    html += '<div class="settle-section"><div class="settle-head">過去の清算</div>';
    if (past.length === 0) {
      html += '<div class="settle-sub">まだ清算の記録はありません。</div>';
    } else {
      html += past.map(function (s) {
        var transfers = Settle.transferList(s);
        var undoable = Settle.canUndo(settlementsOf(currentGroup), s.id);
        return '<div class="past-settlement' + (undoable ? '' : ' old') + '">' +
          '<div class="past-head">' +
            '<span class="past-date">' + esc(dateTime(s.createdAt)) + '</span>' +
            '<span class="past-count">対象 ' + Settle.targetCount(s) + ' 件</span>' +
            (Settle.allDone(s) ? '<span class="past-done-badge">完了</span>' : '') +
          '</div>' +
          transfers.map(function (t) {
            return '<label class="transfer-row' + (t.done ? ' done' : '') + '">' +
              '<input type="checkbox"' + (t.done ? ' checked' : '') +
              ' onchange="toggleTransferDone(\\'' + s.id + '\\', \\'' + t.id + '\\', this.checked)">' +
              '<span class="transfer-names">' + esc(t.fromName || memberName(members, t.from)) +
              ' → ' + esc(t.toName || memberName(members, t.to)) + '</span>' +
              '<span class="transfer-amount">' + money(t.amount) + '</span></label>';
          }).join('') +
          '<div class="past-foot">' +
            (undoable
              ? '<button class="btn btn-secondary btn-sm" onclick="doUndoSettlement(\\'' +
                s.id + '\\')">この清算を取り消す</button>'
              : '<span class="past-note">取り消せるのは最新の清算のみです</span>') +
          '</div></div>';
      }).join('');
    }
    html += '</div>';

    $('settlementContent').innerHTML = html;
  }

  /** 「この内容で清算する」 */
  function doConfirmSettlement() {
    if (!currentCode || !currentGroup) return;
    var members = memberList(currentGroup);
    var pays = paymentList(currentGroup);
    if (Settle.pickPending(pays).length) {
      toast('金額確認中の支払いがあります。先に金額を確定してください', 'error');
      return;
    }
    var me = Auth.user();
    var settlement = Settle.buildSettlement(members, pays, {
      uid: me ? me.uid : '', now: Date.now()
    });
    if (!settlement) { toast('清算する貸し借りがありません'); return; }

    var n = Object.keys(settlement.paymentIds).length;
    var m = Settle.transferList(settlement).length;
    if (!confirm('未清算の支払い ' + n + ' 件を清算として記録します。\\n送金は ' + m +
      ' 本です。\\n\\n記録すると、この ' + n + ' 件は編集・削除できなくなります（取り消しは可能）。')) return;

    var btn = $('settleConfirmBtn');
    if (btn) { btn.disabled = true; btn.textContent = '記録中…'; }
    Store.confirmSettlement(currentCode, settlement).then(function () {
      toast('清算を記録しました');
      renderSettlement();
    }).catch(function (err) {
      if (btn) { btn.disabled = false; btn.textContent = 'この内容で清算する'; }
      fail('清算を記録できませんでした')(err);
    });
  }

  /** 送金 1 本のチェック（他の端末にもそのまま届く） */
  function toggleTransferDone(sid, tid, done) {
    if (!currentCode) return;
    Store.setTransferDone(currentCode, sid, tid, done)
      .catch(fail('送金のチェックを更新できませんでした'));
  }

  /** 清算の取り消し（最新の 1 件だけ） */
  function doUndoSettlement(sid) {
    if (!currentCode || !currentGroup) return;
    var all = settlementsOf(currentGroup);
    if (!Settle.canUndo(all, sid)) {
      toast('取り消せるのは最新の清算のみです', 'error');
      return;
    }
    var s = all[sid];
    if (!s) return;
    var n = Settle.targetCount(s);
    var msg = Settle.hasAnyDone(s)
      ? '送金チェックが入っています。本当にこの清算を取り消しますか？\\n' +
        'チェックの記録も消えます（支払い ' + n + ' 件は未清算に戻ります）。'
      : 'この清算を取り消しますか？\\n支払い ' + n + ' 件が未清算に戻ります。';
    if (!confirm(msg)) return;

    Store.undoSettlement(currentCode, sid, s.paymentIds || {}).then(function () {
      toast('清算を取り消しました');
      renderSettlement();
    }).catch(fail('清算を取り消せませんでした'));
  }"""))

# ⑩ global に出す
REPLACEMENTS.append((
    "清算まわりを global に出す",
    """  root.openSettlement = openSettlement;""",
    """  root.openSettlement = openSettlement;
  root.doConfirmSettlement = doConfirmSettlement;
  root.toggleTransferDone = toggleTransferDone;
  root.doUndoSettlement = doUndoSettlement;
  root.setBalanceMode = setBalanceMode;
  root.lockedNotice = lockedNotice;
  root.onPendingToggle = onPendingToggle;"""))


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
