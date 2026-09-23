/*
 * settle.js — 清算（イベント化）まわりの純粋ロジック
 *
 * DOM・Firebase に依存しない。
 * ブラウザ: <script src="js/settle.js"> で window.Settle
 * Node    : require('./js/settle.js')
 *
 * 役割:
 *   ・計算に入れる支払いを選ぶ（未清算 かつ 金額確認中でない）
 *   ・選んだ支払いだけを js/calc.js に渡して送金リストを作り、
 *     清算レコード（settlements/{sid}）の中身を組み立てる
 *   ・過去の清算のうち「取り消してよいのは最新の 1 件だけ」を判定する
 *
 * 【重要】calc.js（按分・残高・清算の計算そのもの）には一切触らない。
 * 絞り込みは calc.js に渡す**前**にここで行う。
 */
(function (root, Calc) {
  'use strict';

  // ---- 入力の正規化 ---------------------------------------------------

  /** payments（配列でも {pid:{...}} でも）を id 付きの配列にする */
  function asPayments(payments) {
    return Calc.normalizePayments(payments);
  }

  /** settlements（{sid:{...}} でも配列でも）を id 付きの配列にする */
  function asSettlements(settlements) {
    if (!settlements) return [];
    if (Array.isArray(settlements)) {
      return settlements.map(function (s, i) {
        return Object.assign({}, s, { id: s && s.id != null ? s.id : String(i) });
      });
    }
    return Object.keys(settlements).map(function (id) {
      var s = settlements[id] || {};
      return Object.assign({}, s, { id: s.id != null ? s.id : id });
    });
  }

  // ---- 計算に入れる支払いを選ぶ ---------------------------------------

  /**
   * 未清算かつ金額確認中でない支払い（＝残高・清算の計算対象）。
   * ・settlementId が null / undefined のもの
   * ・pending が true でないもの（金額確認中は計算から外す。§5.3.1）
   */
  function pickUnsettled(payments) {
    return asPayments(payments).filter(function (p) {
      return (p.settlementId == null) && p.pending !== true;
    });
  }

  /** 金額確認中の支払い（§5.3.1）*/
  function pickPending(payments) {
    return asPayments(payments).filter(function (p) { return p.pending === true; });
  }

  /** 清算済みの支払い（settlementId が入っているもの）*/
  function pickSettled(payments) {
    return asPayments(payments).filter(function (p) { return p.settlementId != null; });
  }

  /** 累計表示用: 金額確認中だけを外した全支払い（清算済みも含む。§5.4 の「累計を見る」）*/
  function pickAllButPending(payments) {
    return asPayments(payments).filter(function (p) { return p.pending !== true; });
  }

  // ---- 清算レコードの組み立て -----------------------------------------

  /** 送金の ID。並べたときに順番が崩れないよう 3 桁でそろえる */
  function transferId(i) {
    var n = String(i + 1);
    while (n.length < 3) n = '0' + n;
    return 't' + n;
  }

  /**
   * 「この内容で清算する」で書き込む中身を組み立てる。
   *
   * @param {Array|Object} members グループのメンバー
   * @param {Array|Object} payments グループの支払い（全部渡してよい。中で絞る）
   * @param {Object} opts { uid, now }
   * @returns {Object|null} {
   *   createdAt, createdBy,
   *   transfers: { tid: { from, to, fromName, toName, amount, done: false } },
   *   paymentIds: { pid: true }
   * }
   *   対象の支払いが 0 件、または送金が 0 本（貸し借りなし）のときは null
   */
  function buildSettlement(members, payments, opts) {
    var o = opts || {};
    var targets = pickUnsettled(payments);
    if (targets.length === 0) return null;

    var txns = Calc.calcSettlement(members, targets);
    if (txns.length === 0) return null;

    var transfers = {};
    txns.forEach(function (t, i) {
      transfers[transferId(i)] = {
        from: t.fromId,
        to: t.toId,
        fromName: t.from,     // 後でメンバー名が変わっても清算時の名前が残るように
        toName: t.to,
        amount: t.amount,
        done: false
      };
    });

    var paymentIds = {};
    targets.forEach(function (p) { paymentIds[p.id] = true; });

    return {
      createdAt: typeof o.now === 'number' ? o.now : Date.now(),
      createdBy: o.uid == null ? '' : String(o.uid),
      transfers: transfers,
      paymentIds: paymentIds
    };
  }

  // ---- 過去の清算 -----------------------------------------------------

  /** 新しい順（createdAt の降順）に並べた清算の配列 */
  function listSettlements(settlements) {
    return asSettlements(settlements).sort(function (a, b) {
      return ((b.createdAt || 0) - (a.createdAt || 0)) ||
        String(b.id).localeCompare(String(a.id));
    });
  }

  /** いちばん新しい清算（無ければ null）*/
  function latestSettlement(settlements) {
    var list = listSettlements(settlements);
    return list.length ? list[0] : null;
  }

  /**
   * 取り消してよいのは最新の 1 件だけ（古いものを取り消すと計算順が崩れる。§5.5）
   */
  function canUndo(settlements, sid) {
    var latest = latestSettlement(settlements);
    return !!latest && String(latest.id) === String(sid);
  }

  /** 送金チェックが 1 つでも入っているか（取り消し確認の文言を強めるため）*/
  function hasAnyDone(settlement) {
    var t = settlement && settlement.transfers;
    if (!t) return false;
    return Object.keys(t).some(function (k) { return !!(t[k] && t[k].done); });
  }

  /** 送金が 1 本以上あって、全部チェック済みか（「完了」バッジ用）*/
  function allDone(settlement) {
    var t = settlement && settlement.transfers;
    if (!t) return false;
    var keys = Object.keys(t);
    return keys.length > 0 && keys.every(function (k) { return !!(t[k] && t[k].done); });
  }

  /** 送金を並び順（tid の昇順）で配列にする */
  function transferList(settlement) {
    var t = (settlement && settlement.transfers) || {};
    return Object.keys(t).sort().map(function (id) {
      return Object.assign({ id: id }, t[id]);
    });
  }

  /** その清算が対象にした支払いの件数 */
  function targetCount(settlement) {
    return Object.keys((settlement && settlement.paymentIds) || {}).length;
  }

  var api = {
    pickUnsettled: pickUnsettled,
    pickPending: pickPending,
    pickSettled: pickSettled,
    pickAllButPending: pickAllButPending,
    buildSettlement: buildSettlement,
    listSettlements: listSettlements,
    latestSettlement: latestSettlement,
    canUndo: canUndo,
    hasAnyDone: hasAnyDone,
    allDone: allDone,
    transferList: transferList,
    targetCount: targetCount,
    transferId: transferId
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Settle = api;
})(
  typeof globalThis !== 'undefined' ? globalThis : this,
  (typeof module !== 'undefined' && module.exports) ? require('./calc.js')
    : (typeof globalThis !== 'undefined' ? globalThis : this).Calc
);
