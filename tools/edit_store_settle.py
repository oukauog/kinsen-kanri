# -*- coding: utf-8 -*-
"""
工事3: js/store.js に清算レコードの読み書きと、清算済み支払いのロックを足す。

足すもの:
  ・confirmSettlement(code, settlement) 1 回の多パス update で
    settlements/{sid} と対象 payments/{pid}/settlementId を同時に書く（原子的）
  ・setTransferDone(code, sid, tid, done) 送金チェックの更新（doneAt / doneBy つき）
  ・undoSettlement(code, sid, paymentIds) 1 回の多パス update で
    settlementId を null に戻し settlements/{sid} を消す
  ・updatePayment / removePayment は、対象に settlementId が入っていたら
    書かずに拒否する（画面で無効化するだけでなくデータ層でも止める）
  ・addPayment / updatePayment が pending を扱う（pending:true なら amount は 0）

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_store_settle.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "store.js")

REPLACEMENTS = []

# ① 冒頭コメント（データモデルに settlements を書き足す）
REPLACEMENTS.append((
    "冒頭コメントに settlements を追記",
    """ *   groups/{code}/payments/{pid}   : { date, memo, payerId, amount,
 *                                      participants:{mid:true}, settlementId, pending,
 *                                      createdBy, createdAt, updatedAt }""",
    """ *   groups/{code}/payments/{pid}   : { date, memo, payerId, amount,
 *                                      participants:{mid:true}, settlementId, pending,
 *                                      createdBy, createdAt, updatedAt }
 *   groups/{code}/settlements/{sid}: { createdAt, createdBy, paymentIds:{pid:true},
 *                                      transfers/{tid}: { from, to, fromName, toName,
 *                                                         amount, done, doneAt?, doneBy? } }"""))

# ② 清算済みの支払いは編集・削除させない（データ層の防波堤）
REPLACEMENTS.append((
    "清算済みロックの共通処理を追加",
    """  // ---- グループの中身 -------------------------------------------------""",
    """  // ---- 清算済みのロック（工事3）---------------------------------------

  var LOCKED_MSG = '清算済みの支払いは編集できません。先に清算を取り消してください';

  /** 拒否を、書き込み失敗と同じ道（onWriteError）に流す */
  function rejectLocked(op) {
    var err = new Error(LOCKED_MSG);
    err.code = 'KK_SETTLED_LOCKED';
    err.__kkReported = true;
    if (writeErrorHandler) {
      try { writeErrorHandler(op, err); } catch (e) { console.error(e); }
    } else {
      console.error(op, err);
    }
    return Promise.reject(err);
  }

  /**
   * 対象の支払いが清算済みでないことを確かめてから続きを実行する。
   * 画面側で編集ボタンを無効にしているが、他端末で清算が確定した直後など
   * すれ違いが起きうるので、書き込む直前にもう一度見る。
   */
  function ifNotSettled(code, pid, op, fn) {
    return ref('groups/' + code + '/payments/' + pid + '/settlementId').once('value')
      .then(function (s) {
        if (s.val() != null) return rejectLocked(op);
        return fn();
      });
  }

  // ---- グループの中身 -------------------------------------------------"""))

# ③ addPayment が pending を扱う
REPLACEMENTS.append((
    "addPayment が金額確認中を扱う",
    """  function addPayment(code, p) {
    var myUid = uid();
    var pid = ref('groups/' + code + '/payments').push().key;
    return wrapWrite('支払いを記録できませんでした',
      ref('groups/' + code + '/payments/' + pid).set({
      date: p.date,
      memo: p.memo || '',
      payerId: p.payerId,
      amount: p.amount,
      participants: p.participants,
      settlementId: null,   // 工事3 の清算レコード用。今は必ず null
      pending: false,       // 工事3 の「金額確認中」用。今は必ず false""",
    """  function addPayment(code, p) {
    var myUid = uid();
    var pid = ref('groups/' + code + '/payments').push().key;
    var pending = p.pending === true;
    return wrapWrite('支払いを記録できませんでした',
      ref('groups/' + code + '/payments/' + pid).set({
      date: p.date,
      memo: p.memo || '',
      payerId: p.payerId,
      amount: pending ? 0 : p.amount,   // 金額確認中は 0 で持つ（§5.3.1）
      participants: p.participants,
      settlementId: null,   // 清算するとここに sid が入る
      pending: pending,     // 金額確認中（残高・清算から外れる）"""))

# ④ updatePayment / removePayment にロックと pending
REPLACEMENTS.append((
    "updatePayment にロックと金額確認中を足す",
    """  /** 支払いの更新。触ったフィールドだけ update する（createdBy / createdAt は保つ） */
  function updatePayment(code, pid, p) {
    return wrapWrite('支払いを更新できませんでした',
      ref('groups/' + code + '/payments/' + pid).update({
        date: p.date,
        memo: p.memo || '',
        payerId: p.payerId,
        amount: p.amount,
        participants: p.participants,
        updatedAt: FB.now()
      }));
  }

  function removePayment(code, pid) {
    return wrapWrite('支払いを削除できませんでした',
      ref('groups/' + code + '/payments/' + pid).remove());
  }""",
    """  /**
   * 支払いの更新。触ったフィールドだけ update する（createdBy / createdAt は保つ）。
   * 清算済みのものは書かずに拒否する（工事3）。
   */
  function updatePayment(code, pid, p) {
    var pending = p.pending === true;
    return ifNotSettled(code, pid, '支払いを更新できませんでした', function () {
      return wrapWrite('支払いを更新できませんでした',
        ref('groups/' + code + '/payments/' + pid).update({
          date: p.date,
          memo: p.memo || '',
          payerId: p.payerId,
          amount: pending ? 0 : p.amount,
          participants: p.participants,
          pending: pending,
          updatedAt: FB.now()
        }));
    });
  }

  /** 支払いの削除。清算済みのものは消さずに拒否する（工事3）。 */
  function removePayment(code, pid) {
    return ifNotSettled(code, pid, '支払いを削除できませんでした', function () {
      return wrapWrite('支払いを削除できませんでした',
        ref('groups/' + code + '/payments/' + pid).remove());
    });
  }"""))

# ⑤ 清算レコードの読み書き
REPLACEMENTS.append((
    "清算レコードの読み書きを追加",
    """  // ---- 移行（旧 rooms からの取り込み。工事2）--------------------------""",
    """  // ---- 清算（工事3）---------------------------------------------------

  /**
   * 清算を確定する。**1 回の多パス update** で
   *   ・settlements/{sid} を書く
   *   ・対象の payments/{pid}/settlementId に sid を入れる
   * を同時に行う（途中で切れて「片方だけ」にならないように）。
   *
   * @param {string} code グループの共有コード
   * @param {Object} settlement Settle.buildSettlement の戻り値
   * @returns {Promise<string>} 作成した清算の ID（sid）
   */
  function confirmSettlement(code, settlement) {
    var sid = ref('groups/' + code + '/settlements').push().key;
    var updates = {};
    updates['settlements/' + sid] = settlement;
    Object.keys(settlement.paymentIds || {}).forEach(function (pid) {
      updates['payments/' + pid + '/settlementId'] = sid;
    });
    return wrapWrite('清算を記録できませんでした',
      ref('groups/' + code).update(updates)).then(function () { return sid; });
  }

  /** 送金 1 本のチェックを付け外しする（誰がいつ付けたかも残す） */
  function setTransferDone(code, sid, tid, done) {
    var myUid = uid();
    var base = 'groups/' + code + '/settlements/' + sid + '/transfers/' + tid;
    return wrapWrite('送金のチェックを更新できませんでした',
      ref(base).update({
        done: !!done,
        doneAt: done ? FB.now() : null,
        doneBy: done ? myUid : null
      }));
  }

  /**
   * 清算を取り消す。**1 回の多パス update** で
   *   ・対象の payments/{pid}/settlementId を null に戻す
   *   ・settlements/{sid} を消す
   * を同時に行う。取り消せるのは最新の 1 件だけ（判定は Settle.canUndo、画面側）。
   *
   * @param {Object|Array} paymentIds { pid: true } か [pid]
   */
  function undoSettlement(code, sid, paymentIds) {
    var ids = Array.isArray(paymentIds) ? paymentIds : Object.keys(paymentIds || {});
    var updates = {};
    ids.forEach(function (pid) {
      updates['payments/' + pid + '/settlementId'] = null;
    });
    updates['settlements/' + sid] = null;
    return wrapWrite('清算を取り消せませんでした',
      ref('groups/' + code).update(updates));
  }

  // ---- 移行（旧 rooms からの取り込み。工事2）--------------------------"""))

# ⑥ 公開
REPLACEMENTS.append((
    "公開する関数に清算まわりを追加",
    """    removePayment: removePayment,
    readRoom: readRoom,""",
    """    removePayment: removePayment,
    confirmSettlement: confirmSettlement,
    setTransferDone: setTransferDone,
    undoSettlement: undoSettlement,
    readRoom: readRoom,"""))


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

    # rooms へ書き込むコードが混ざっていないこと（工事2 からの継続確認）
    import re
    for m in re.finditer(r"ref\('rooms/[^']*'\)\s*\.\s*(\w+)", out):
        assert m.group(1) == "once", "rooms へ once 以外の操作がある: " + m.group(0)

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
