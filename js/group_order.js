/*
 * group_order.js — 左サイドバーのグループ一覧の並び順（工事5）
 *
 * ブラウザ: <script src="js/group_order.js"> で window.KKGroupOrder
 * Node    : require('./js/group_order.js')（sortCodes / nextOrder のテスト用）
 *
 * 並び順は人ごとの好み。users/{uid}/groups/{code}: { joinedAt, order? } の order で持つ
 * （groups/{code} 側には何も書かない。他のメンバーには影響しない）。
 *
 * 決めごと:
 *   ・表示順のキー: order が数値なら order、無ければ joinedAt（それも無ければ 0）。昇順。
 *     同点はコードの文字列順
 *   ・order が文字列や null のときは「無いもの」として扱う
 *   ・order の無い既存グループはバックフィルしない（並べるときだけ joinedAt を使う）
 *   ・新規作成・コード参加は nextOrder（今の表示順キーの最大 + 1、空なら 0）で一番下に入る
 *   ・ドラッグ＆ドロップで並びが確定したら、その表示順で 0, 1, 2, … を書き直す
 *     （書くのは store.js の setGroupOrder）
 *
 * sortCodes / nextOrder は DOM も Firebase も使わない純粋関数。
 * attach だけが DOM と SortableJS（window.Sortable、CDN）を使う。
 */
(function (root) {
  'use strict';

  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /** 1 グループの表示順キー */
  function sortKey(entry) {
    if (!entry || typeof entry !== 'object') return 0;
    if (isNum(entry.order)) return entry.order;
    if (isNum(entry.joinedAt)) return entry.joinedAt;
    return 0;
  }

  /**
   * 表示順に並べたコードの配列を返す
   * @param {Object} myGroups { code: { joinedAt, order? } }
   * @returns {string[]}
   */
  function sortCodes(myGroups) {
    var g = myGroups || {};
    return Object.keys(g).sort(function (a, b) {
      var ka = sortKey(g[a]);
      var kb = sortKey(g[b]);
      if (ka !== kb) return ka < kb ? -1 : 1;
      return a < b ? -1 : (a > b ? 1 : 0);
    });
  }

  /**
   * 新しく入れるグループの order（一覧の一番下に来る値）
   * @param {Object} myGroups { code: { joinedAt, order? } }
   * @returns {number} 表示順キーの最大 + 1。一覧が空なら 0
   */
  function nextOrder(myGroups) {
    var g = myGroups || {};
    var codes = Object.keys(g);
    if (codes.length === 0) return 0;
    var max = -Infinity;
    codes.forEach(function (c) {
      var k = sortKey(g[c]);
      if (k > max) max = k;
    });
    return max + 1;
  }

  // ---- ドラッグ＆ドロップ（SortableJS）----------------------------------

  var warned = false;

  /**
   * #groupList に SortableJS を付ける。
   * listEl の innerHTML が描画のたびに置き換わっても、インスタンスはコンテナに付いているので
   * 1 回付ければよい。付け済みなら何もしない。
   * window.Sortable が無いとき（CDN が読めない・通し確認ページ）は console.warn を 1 回だけ出して
   * 何もしない（一覧の表示と選択は今までどおり。並び替えだけできない）。
   * @param {HTMLElement} listEl
   * @param {function(string[])} onReorder ドロップ後の DOM の順（data-code）で呼ばれる
   */
  function attach(listEl, onReorder) {
    if (!listEl || listEl.__kkSortable) return;
    var Sortable = root.Sortable;
    if (typeof Sortable === 'undefined' || !Sortable || typeof Sortable.create !== 'function') {
      if (!warned) {
        warned = true;
        console.warn('SortableJS を読み込めなかったため、グループの並び替えは使えません');
      }
      return;
    }
    listEl.__kkSortable = Sortable.create(listEl, {
      // つまみだけで動かす。行全体の長押しは、スマホで一覧のスクロールやタップ選択と取り合いになる
      handle: '.group-item-handle',
      draggable: '.group-item',
      animation: 150,
      ghostClass: 'group-item-ghost',
      onEnd: function (evt) {
        if (evt && evt.oldIndex === evt.newIndex) return;
        var codes = Array.prototype.map.call(
          listEl.querySelectorAll('.group-item[data-code]'),
          function (el) { return el.getAttribute('data-code'); });
        if (onReorder) onReorder(codes);
      }
    });
  }

  var api = {
    sortKey: sortKey,
    sortCodes: sortCodes,
    nextOrder: nextOrder,
    attach: attach
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.KKGroupOrder = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
