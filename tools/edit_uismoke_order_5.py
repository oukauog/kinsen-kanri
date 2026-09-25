# -*- coding: utf-8 -*-
"""
工事5: 画面の通し確認に「サイドバーの並び順」の確認を足す。

確認すること（ドラッグそのものはヘッドレスでは見ない。花井の実機検収で見る）:
  (a) グループを新規作成すると一覧の一番下に入る
  (b) コード参加でも一番下に入る
  (c) users/{uid}/groups/{code} への set に order（= 作成・参加前の一覧の nextOrder）が入っている
  (d) setGroupOrder(['B','A','C']) の update のキーが B/order=0, A/order=1, C/order=2 になる
      （あわせて、実在のコードで setGroupOrder すると、その順でサイドバーが並び、joinedAt は変わらない）
  (e) 各 .group-item に data-code とつまみがある。削除済み（missing）の行にはつまみが無いが並びには残る。
      つまみを押しても selectGroup は起きない
  (f) window.Sortable が無くても一覧の描画と選択が動く。console.warn（SortableJS）は 1 回だけ

console.warn は、通し確認のスクリプトが読み込まれた時点で差し替えて数える
（ログインは通し確認が _signIn を呼んでから起きるので、attach の警告より先に差し替わっている）。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_order_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_driver.js")

EDITS = [
# ① console.warn を数える
("""  // confirm / alert はヘッドレスでは出せないので差し替える
""",
"""  // 工事5: console.warn を数える（SortableJS が無いときの警告が 1 回だけか見る）
  var warns = [];
  var origWarn = console.warn;
  console.warn = function () {
    warns.push(Array.prototype.join.call(arguments, ' '));
    return origWarn.apply(console, arguments);
  };
  // 工事5: サイドバーの行のコード（表示順）
  function rowCodes() {
    return Array.prototype.map.call($('groupList').querySelectorAll('.group-item'),
      function (el) { return el.getAttribute('data-code'); });
  }
  function myGroupsNow() {
    return JSON.parse(JSON.stringify(root.KKStore._data.users['u-test'].groups));
  }
  function lastWrite(op, path) {
    var ws = root.KKStore._writes.filter(function (w) { return w.op === op && w.path === path; });
    return ws.length ? ws[ws.length - 1] : null;
  }

  // confirm / alert はヘッドレスでは出せないので差し替える
"""),
# ①' 段をまたいで持つ値の入れ物
("""    var code = null;
""",
"""    var code = null;
    var ord = {};   // 工事5 の確認で、段（.then）をまたいで持つ値
"""),
# ② 工事4d-B の前に確認を足す
("""      // ══ 工事4d-B: スマホ幅で過去の清算の行がはみ出さないこと ══
""",
"""      // ══ 工事5: サイドバーの並び順 ══
      .then(function () {
        // (f) 通し確認ページには SortableJS を入れていない
        var sw = warns.filter(function (w) { return w.indexOf('SortableJS') >= 0; });
        check('並び順: 通し確認ページには window.Sortable が無い', typeof window.Sortable === 'undefined');
        check('並び順: Sortable が無いときの console.warn は 1 回だけ', sw.length === 1,
          sw.length + ' 回: ' + sw.join(' / '));
        var n = Object.keys(myGroupsNow()).length;
        check('並び順: Sortable が無くても一覧が全件描かれる',
          $('groupList').querySelectorAll('.group-item').length === n,
          $('groupList').querySelectorAll('.group-item').length + ' 行 / ' + n + ' 件');

        // (a)(c) 新規作成
        ord.before = myGroupsNow();
        root.openNewGroupModal();
        $('newGroupName').value = 'テスト並び末尾';
        ['た', 'ち'].forEach(function (nm) {
          $('newMemberInput').value = nm;
          root.addNewMember();
        });
        root.createGroup();
        return wait(100);
      })
      .then(function () {
        var before = ord.before;
        var now = myGroupsNow();
        var added = Object.keys(now).filter(function (c) { return !(c in before); });
        var codes = rowCodes();
        check('並び順: 新規作成したグループが 1 件増える', added.length === 1, added.join(','));
        check('並び順: 新規作成したグループは一覧の一番下に入る',
          added.length === 1 && codes[codes.length - 1] === added[0],
          codes.join(',') + ' / 追加 ' + added.join(','));
        var w = added.length === 1 ? lastWrite('set', 'users/u-test/groups/' + added[0]) : null;
        var expect = root.KKGroupOrder.nextOrder(before);
        check('並び順: 新規作成の users/{uid}/groups への set に order（最大 + 1）が入る',
          !!w && w.value.order === expect && typeof w.value.joinedAt === 'number',
          w ? JSON.stringify(w.value) + ' 期待 order=' + expect : '(書き込みが無い)');

        // (b)(c) コード参加
        root.KKStore._seedGroup('ORDJ01', 'テスト参加末尾', ['つ', 'て']);
        ord.before = myGroupsNow();
        root.openJoinModal();
        $('joinCodeInput').value = 'ORDJ01';
        root.doJoin();
        return wait(120);
      })
      .then(function () {
        var before = ord.before;
        var codes = rowCodes();
        check('並び順: コードで参加したグループも一覧の一番下に入る',
          codes[codes.length - 1] === 'ORDJ01', codes.join(','));
        var w = lastWrite('set', 'users/u-test/groups/ORDJ01');
        var expect = root.KKGroupOrder.nextOrder(before);
        check('並び順: コード参加の users/{uid}/groups への set に order（最大 + 1）が入る',
          !!w && w.value.order === expect && typeof w.value.joinedAt === 'number',
          w ? JSON.stringify(w.value) + ' 期待 order=' + expect : '(書き込みが無い)');

        // (d) setGroupOrder の update のキー
        root.KKStore.setGroupOrder(['B', 'A', 'C']);
        var u = lastWrite('update', 'users/u-test/groups');
        check('並び順: setGroupOrder([B,A,C]) の update が B/order=0, A/order=1, C/order=2',
          !!u && JSON.stringify(u.value) === JSON.stringify({ 'B/order': 0, 'A/order': 1, 'C/order': 2 }),
          u ? JSON.stringify(u.value) : '(update が無い)');
        // 確認用に作られた B / A / C を片付ける
        ['B', 'A', 'C'].forEach(function (c) { root.KKStore.leaveGroup(c); });
        return wait(80);
      })
      .then(function () {
        // 実在のコードで並べ替えると、その順で描かれる（ドロップ後に Firebase から戻ってくる流れ）
        var before = myGroupsNow();
        var reversed = rowCodes().slice().reverse();
        ord.before = before;
        ord.want = reversed;
        root.KKStore.setGroupOrder(reversed);
        return wait(100);
      })
      .then(function () {
        var before = ord.before;
        var want = ord.want;
        var now = myGroupsNow();
        check('並び順: setGroupOrder で書いた順にサイドバーが並ぶ',
          JSON.stringify(rowCodes()) === JSON.stringify(want), rowCodes().join(',') + ' / 期待 ' + want.join(','));
        check('並び順: setGroupOrder は joinedAt を変えない',
          Object.keys(before).every(function (c) { return now[c] && now[c].joinedAt === before[c].joinedAt; }));
        check('並び順: setGroupOrder の後は order が 0..n-1',
          want.every(function (c, i) { return now[c].order === i; }));

        // (e) 削除済みの行を作る（本体の無いコードを自分の一覧に入れる）
        root.KKStore._seedMyGroup('GONE01', { joinedAt: 1 });
        return wait(100);
      })
      .then(function () {
        var items = $('groupList').querySelectorAll('.group-item');
        var noCode = Array.prototype.filter.call(items, function (el) { return !el.getAttribute('data-code'); });
        check('並び順: 各 .group-item に data-code がある', items.length > 0 && noCode.length === 0,
          noCode.length + ' 行に無い');
        var normal = $('groupList').querySelectorAll('.group-item:not(.missing)');
        var noHandle = Array.prototype.filter.call(normal, function (el) {
          return el.querySelectorAll('.group-item-handle').length !== 1;
        });
        check('並び順: 削除済みでない行には右端につまみが 1 つある', normal.length > 0 && noHandle.length === 0,
          noHandle.length + ' 行が不正');
        var gone = $('groupList').querySelector('.group-item.missing[data-code="GONE01"]');
        check('並び順: 削除済みの行は並びの中に残る', !!gone && rowCodes().indexOf('GONE01') >= 0,
          rowCodes().join(','));
        check('並び順: 削除済みの行にはつまみが無い', !!gone && !gone.querySelector('.group-item-handle'));

        // つまみを押しても選択は変わらない
        var active = $('groupList').querySelector('.group-item.active');
        var activeCode = active ? active.getAttribute('data-code') : null;
        var other = Array.prototype.filter.call(normal, function (el) {
          return el.getAttribute('data-code') !== activeCode;
        })[0];
        ord.other = other ? other.getAttribute('data-code') : null;
        ord.active = activeCode;
        if (other) other.querySelector('.group-item-handle').click();
        return wait(60);
      })
      .then(function () {
        var other = ord.other;
        var active = $('groupList').querySelector('.group-item.active');
        check('並び順: つまみを押しても selectGroup は起きない（選択中のグループが変わらない）',
          !!other && (active ? active.getAttribute('data-code') : null) === ord.active,
          '押した ' + other + ' / 選択中 ' + (active ? active.getAttribute('data-code') : '(なし)'));

        // (f) 名前を押せば今までどおり選べる
        var row = $('groupList').querySelector('.group-item[data-code="' + other + '"] .group-item-name');
        if (row) row.click();
        return wait(80);
      })
      .then(function () {
        var other = ord.other;
        var active = $('groupList').querySelector('.group-item.active');
        check('並び順: Sortable が無くても行を押せばグループを選べる',
          !!active && active.getAttribute('data-code') === other,
          active ? active.getAttribute('data-code') : '(選択なし)');
        root.KKStore.leaveGroup('GONE01');
        return wait(60);
      })

      // ══ 工事4d-B: スマホ幅で過去の清算の行がはみ出さないこと ══
"""),
]


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "工事5: サイドバーの並び順" in src:
        print("すでに適用済みです。何もしません。")
        return 0
    errors = []
    out = src
    for before, after in EDITS:
        n = out.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
            continue
        out = out.replace(fix(before), fix(after), 1)
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
