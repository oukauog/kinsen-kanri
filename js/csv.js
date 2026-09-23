/*
 * csv.js — CSV 文字列を作る純粋ロジック（工事4a）
 *
 * DOM・Firebase に依存しない（ダウンロードは ui.js 側）。
 * ブラウザ: <script src="js/csv.js"> で window.Csv
 * Node    : require('./js/csv.js')
 *
 * 決めごと:
 *   ・先頭に UTF-8 BOM を付ける（Excel で開いたときの文字化け防止。v1 と同じ）
 *   ・改行は CRLF（v1 と同じ）
 *   ・計算は js/calc.js、対象の絞り込みは js/settle.js に任せる（ここでは作らない）
 *   ・金額確認中（pending）は、どちらの残高モードでも計算に入れない（工事3 と同じ）
 */
(function (root, Calc, Settle) {
  'use strict';

  var BOM = '﻿';
  var EOL = '\r\n';

  /**
   * CSV の 1 セル。カンマ・改行・ダブルクォートを含むときだけ "…" で囲み、" は "" にする。
   */
  function escapeCell(v) {
    var s = (v == null) ? '' : String(v);
    if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function toLines(rows) {
    return BOM + rows.map(function (row) {
      return row.map(escapeCell).join(',');
    }).join(EOL) + EOL;
  }

  /** group は { members } でも、メンバーそのもの（配列 / オブジェクト）でも受ける */
  function membersOf(group) {
    if (group && group.members) return Calc.normalizeMembers(group.members);
    return Calc.normalizeMembers(group || {});
  }

  function nameOf(members, mid) {
    for (var i = 0; i < members.length; i++) if (members[i].id === mid) return members[i].name;
    return '?';
  }

  /** ミリ秒 → 「2026/09/24 18:30」（ui.js の表示と同じ形） */
  function dateTime(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '/' + p(d.getMonth() + 1) + '/' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** 画面の履歴と同じ並び（日付の降順 → createdAt の降順） */
  function sortedPayments(payments) {
    return Calc.normalizePayments(payments).sort(function (a, b) {
      return String(b.date || '').localeCompare(String(a.date || '')) ||
        ((b.createdAt || 0) - (a.createdAt || 0));
    });
  }

  /**
   * 支払い一覧の CSV。
   * 列: 日付, メモ, 支払った人, 金額, 割り勘対象, 1人あたり, 清算状態
   * 清算状態: 未清算 / 清算済み（YYYY/MM/DD HH:mm） / 金額確認中
   */
  function paymentsCsv(group, payments, settlements) {
    var members = membersOf(group);
    var ss = settlements || {};
    var rows = [['日付', 'メモ', '支払った人', '金額', '割り勘対象', '1人あたり', '清算状態']];

    sortedPayments(payments).forEach(function (p) {
      var n = p.participants.length;
      var per = n > 0 ? Math.round(p.amount / n) : 0;
      var parts = p.participants.map(function (mid) {
        return nameOf(members, mid);
      }).join('・');

      var state;
      if (p.pending === true) {
        state = '金額確認中';
      } else if (p.settlementId != null) {
        var s = ss[p.settlementId];
        var when = s ? dateTime(s.createdAt) : '';
        state = when ? '清算済み（' + when + '）' : '清算済み';
      } else {
        state = '未清算';
      }

      rows.push([p.date, p.memo || '', nameOf(members, p.payerId), p.amount, parts, per, state]);
    });

    return toLines(rows);
  }

  /**
   * 残高の CSV。
   * 1 行目はコメント行（# 残高（未清算のみ） / # 残高（累計））。
   * 列: メンバー, 払った合計, 負担分, 残高
   * @param {string} mode 'unsettled'（未清算のみ）か 'all'（累計）
   */
  function balancesCsv(group, payments, mode) {
    var members = membersOf(group);
    var isAll = (mode === 'all');
    var target = isAll ? Settle.pickAllButPending(payments) : Settle.pickUnsettled(payments);
    var bal = Calc.calcBalances(members, target);

    var paid = {};
    members.forEach(function (m) { paid[m.id] = 0; });
    target.forEach(function (p) {
      if (!(p.payerId in paid)) paid[p.payerId] = 0;
      paid[p.payerId] += p.amount;
    });

    var rows = [
      ['# 残高（' + (isAll ? '累計' : '未清算のみ') + '）'],
      ['メンバー', '払った合計', '負担分', '残高']
    ];
    // 画面の残高カードと同じ並び（マイナスが大きい人が先頭）
    members.slice().sort(function (a, b) {
      return (bal[a.id] || 0) - (bal[b.id] || 0);
    }).forEach(function (m) {
      var b = bal[m.id] || 0;
      var pd = paid[m.id] || 0;
      rows.push([m.name, Math.round(pd), Math.round(pd - b), Math.round(b)]);
    });

    return toLines(rows);
  }

  /** ファイル名用。Windows で使えない文字と空白を置き換える */
  function safeFileName(s) {
    return String(s == null ? '' : s).replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, '_');
  }

  /** YYYYMMDD */
  function stamp(d) {
    var t = d || new Date();
    var p = function (n) { return String(n).padStart(2, '0'); };
    return t.getFullYear() + p(t.getMonth() + 1) + p(t.getDate());
  }

  var api = {
    BOM: BOM,
    escapeCell: escapeCell,
    paymentsCsv: paymentsCsv,
    balancesCsv: balancesCsv,
    safeFileName: safeFileName,
    stamp: stamp
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Csv = api;
})(
  typeof globalThis !== 'undefined' ? globalThis : this,
  (typeof module !== 'undefined' && module.exports) ? require('./calc.js')
    : (typeof globalThis !== 'undefined' ? globalThis : this).Calc,
  (typeof module !== 'undefined' && module.exports) ? require('./settle.js')
    : (typeof globalThis !== 'undefined' ? globalThis : this).Settle
);
