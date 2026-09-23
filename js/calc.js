/*
 * calc.js — 按分・残高・清算の純粋ロジック（v1 index.html から切り出し）
 *
 * DOM にも Firebase にも依存しない。
 * ブラウザ: <script src="js/calc.js"> で window.Calc に生える
 * Node    : require('./js/calc.js') で同じオブジェクトが取れる
 *
 * 【重要】ここの計算結果は v1（2026-09 時点の index.html）と 1 円も変えない。
 * v1 の癖（支払者が割り勘対象に含まれないと残高合計が 0 にならない等）も
 * そのまま残してある。仕様を変えるときは tests/calc.test.js を先に直すこと。
 */
(function (root) {
  'use strict';

  // ---- 入力の正規化 ---------------------------------------------------
  // v1 は members / participants が配列、v2 は ID キーのオブジェクト。
  // どちらで渡されても同じ結果になるようにここで吸収する。

  // members: [{id,name,order?}] か {mid:{name,order?}} → [{id,name,order}]
  function normalizeMembers(members) {
    if (!members) return [];
    if (Array.isArray(members)) {
      return members.map(function (m, i) {
        return { id: m.id, name: m.name, order: m.order != null ? m.order : i };
      });
    }
    return Object.keys(members).map(function (id, i) {
      var m = members[id] || {};
      return { id: id, name: m.name, order: m.order != null ? m.order : i };
    }).sort(function (a, b) {
      return (a.order - b.order) || String(a.id).localeCompare(String(b.id));
    });
  }

  // participants: ['a','b'] か {a:true,b:true} → ['a','b']
  // オブジェクトのときは値が偽のキーを落とす（{a:true,b:false} → ['a']）
  function normalizeParticipants(participants) {
    if (!participants) return [];
    if (Array.isArray(participants)) return participants.slice();
    return Object.keys(participants).filter(function (k) { return !!participants[k]; });
  }

  // payments: [{...}] か {pid:{...}} → [{id,...}]
  function normalizePayments(payments) {
    if (!payments) return [];
    var list;
    if (Array.isArray(payments)) {
      list = payments.slice();
    } else {
      list = Object.keys(payments).map(function (id) {
        var p = payments[id] || {};
        var o = {};
        for (var k in p) if (Object.prototype.hasOwnProperty.call(p, k)) o[k] = p[k];
        o.id = p.id != null ? p.id : id;
        return o;
      });
    }
    return list.map(function (p) {
      var o = {};
      for (var k in p) if (Object.prototype.hasOwnProperty.call(p, k)) o[k] = p[k];
      o.participants = normalizeParticipants(p.participants);
      o.amount = Number(p.amount) || 0;
      return o;
    });
  }

  // ---- 按分 -----------------------------------------------------------

  // 1 人あたりの負担額（丸めない。v1 は amount / participants.length）
  function share(amount, participantCount) {
    if (!participantCount) return 0;
    return (Number(amount) || 0) / participantCount;
  }

  // ---- 残高 -----------------------------------------------------------

  /**
   * 残高 = 払った合計 − 負担分合計（丸めない浮動小数）
   * v1 の calcBalances と同じ手順:
   *   ・割り勘対象が 0 人の支払いは無視する
   *   ・支払者が対象に含まれるとき  bal[payer] += amount - share
   *   ・対象者（支払者以外）        bal[mid]   -= share
   *   ・支払者が対象に含まれないときは支払者に何も加算しない（v1 の癖。残高合計が 0 にならない）
   * @param {Array|Object} members     メンバー（配列でも ID キーのオブジェクトでも可）
   * @param {Array|Object} payments    そのグループの支払いだけを渡すこと
   * @returns {Object} { mid: 残高 }
   */
  function calcBalances(members, payments) {
    var ms = normalizeMembers(members);
    var ps = normalizePayments(payments);
    var bal = {};
    ms.forEach(function (m) { bal[m.id] = 0; });
    ps.forEach(function (p) {
      var n = p.participants.length;
      if (n === 0) return;
      var per = p.amount / n;
      p.participants.forEach(function (mid) {
        if (!(mid in bal)) bal[mid] = 0;
        if (mid === p.payerId) bal[mid] += p.amount - per;
        else bal[mid] -= per;
      });
    });
    return bal;
  }

  // ---- 清算（貪欲法） -------------------------------------------------

  /**
   * 残高から送金リストを作る（v1 の calcSettlement と同じ貪欲法）
   *   ・|残高| > 0.5 の人だけを対象にする
   *   ・借り（マイナス）・貸し（プラス）をそれぞれ金額の大きい順に並べ、頭から突き合わせる
   *   ・送金額は四捨五入（Math.round）
   * 決定的なので送金の本数も順序も毎回同じになる。
   * @returns {Array} [{ from: 名前, to: 名前, amount: 整数円, fromId, toId }]
   *   from / to は v1 と同じ「名前」。fromId / toId は v2 用の追加（v1 の値は変えていない）
   */
  function calcSettlementFromBalances(members, balances) {
    var ms = normalizeMembers(members);
    var bal = balances || {};
    var debtors = ms.filter(function (m) { return (bal[m.id] || 0) < -0.5; })
      .map(function (m) { return { id: m.id, name: m.name, amount: -(bal[m.id]) }; })
      .sort(function (a, b) { return b.amount - a.amount; });
    var creditors = ms.filter(function (m) { return (bal[m.id] || 0) > 0.5; })
      .map(function (m) { return { id: m.id, name: m.name, amount: bal[m.id] }; })
      .sort(function (a, b) { return b.amount - a.amount; });
    var txns = [], di = 0, ci = 0;
    while (di < debtors.length && ci < creditors.length) {
      var d = debtors[di], c = creditors[ci];
      var amt = Math.min(d.amount, c.amount);
      txns.push({
        from: d.name, to: c.name, amount: Math.round(amt),
        fromId: d.id, toId: c.id
      });
      d.amount -= amt; c.amount -= amt;
      if (d.amount < 0.5) di++;
      if (c.amount < 0.5) ci++;
    }
    return txns;
  }

  /** メンバーと支払いから直接、送金リストを作る（v1 の calcSettlement 相当） */
  function calcSettlement(members, payments) {
    return calcSettlementFromBalances(members, calcBalances(members, payments));
  }

  // ---- 表示用の小道具（v1 と同じ丸め方） ------------------------------

  /** 表示用の金額文字列。v1 の money() と同じ（絶対値を四捨五入して 3 桁区切り） */
  function money(n) {
    return '¥' + Math.abs(Math.round(Number(n) || 0)).toLocaleString();
  }

  var api = {
    normalizeMembers: normalizeMembers,
    normalizeParticipants: normalizeParticipants,
    normalizePayments: normalizePayments,
    share: share,
    calcBalances: calcBalances,
    calcSettlement: calcSettlement,
    calcSettlementFromBalances: calcSettlementFromBalances,
    money: money
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Calc = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
