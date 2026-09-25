# -*- coding: utf-8 -*-
"""
工事5: サイドバーのグループ一覧を「自分で決めた並び順」にする（画面側）。

  js/ui.js
    ・sortedCodes は KKGroupOrder.sortCodes(myGroups) を呼ぶだけにする（五十音順は消す）
    ・renderSidebar: 各 .group-item に data-code を付け、右端につまみ（.group-item-handle）を置く。
      つまみのクリック／タップは stopPropagation して selectGroup を起こさない。
      名前は .group-item-name で包む。削除済み（.missing）の行にはつまみを付けない（並びには残す）
    ・createGroup / joinGroup に KKGroupOrder.nextOrder(myGroups) を渡す（一番下に入る）
    ・ログイン後にサイドバーを最初に描いた後、KKGroupOrder.attach を 1 回だけ呼ぶ。
      ドロップ後は Store.setGroupOrder(codes)。失敗は fail(...) で通知
  css/v2.css
    ・.group-item を横並び（名前 + つまみ）にし、つまみ・ドラッグ中の見た目を足す
  index.html
    ・script タグ 2 行の追加のみ（SortableJS の CDN と js/group_order.js）
  tools/make_uitest.py
    ・通し確認ページでは SortableJS の CDN の行も外す（window.Sortable が無い状態で動くことを確かめるため）

置換対象の一致が「ちょうど 1 つ」であることを、4 ファイルすべてについて確認してから書き戻す
（1 つでも違えば、どのファイルにも何も書かない）。
実行: py -X utf8 tools/edit_ui_grouporder_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UI = [
("""  var Env = root.Env;
""",
"""  var Env = root.Env;
  var GroupOrder = root.KKGroupOrder;
"""),
("""  var myGroups = {};          // { code: { joinedAt } }
""",
"""  var myGroups = {};          // { code: { joinedAt, order? } }
"""),
("""  function sortedCodes() {
    return Object.keys(myGroups).sort(function (a, b) {
      var na = metas[a] && metas[a].name ? metas[a].name : '';
      var nb = metas[b] && metas[b].name ? metas[b].name : '';
      return na.localeCompare(nb, 'ja') || a.localeCompare(b);
    });
  }
""",
"""  /** 表示順（order → 無ければ joinedAt、同点はコード順。js/group_order.js）*/
  function sortedCodes() {
    return GroupOrder.sortCodes(myGroups);
  }
"""),
("""        return '<div class="group-item missing">' +
          '<span class="group-item-name">（削除されたグループ）</span>' +""",
"""        // つまみは付けない（自分では動かせない）が、並びの中には残す
        return '<div class="group-item missing" data-code="' + code + '">' +
          '<span class="group-item-name">（削除されたグループ）</span>' +"""),
("""      return '<div class="group-item' + (code === currentCode ? ' active' : '') + '" ' +
        'onclick="selectGroup(\\'' + code + '\\')">' + esc(name) + '</div>';
    }).join('');
  }
""",
"""      // 右端のつまみ（⋮⋮）でだけ並べ替える。つまみを押しても selectGroup は起こさない
      return '<div class="group-item' + (code === currentCode ? ' active' : '') + '" ' +
        'data-code="' + code + '" onclick="selectGroup(\\'' + code + '\\')">' +
        '<span class="group-item-name">' + esc(name) + '</span>' +
        '<span class="group-item-handle" title="ドラッグで並べ替え" ' +
        'onclick="event.stopPropagation()">&#x22EE;&#x22EE;</span></div>';
    }).join('');
  }

  /** つまみのドラッグ＆ドロップで並びが確定したら、その順で order = 0..n-1 を書く */
  function saveGroupOrder(codes) {
    // 描画とドロップの間に一覧から消えたコードに order だけ書かないよう、今の一覧にあるものに絞る
    var list = codes.filter(function (c) { return !!myGroups[c]; });
    Store.setGroupOrder(list).catch(fail('グループの並び順を保存できませんでした'));
  }
"""),
("""    Store.createGroup(name, newMembers).then(function (code) {""",
"""    Store.createGroup(name, newMembers, GroupOrder.nextOrder(myGroups)).then(function (code) {"""),
("""        return Store.joinGroup(code).then(function () {""",
"""        return Store.joinGroup(code, GroupOrder.nextOrder(myGroups)).then(function () {"""),
("""      Store.watchMyGroups(function (groups) {
        myGroups = groups;
        syncMetaWatchers();
        renderSidebar();
""",
"""      Store.watchMyGroups(function (groups) {
        myGroups = groups;
        syncMetaWatchers();
        renderSidebar();
        // 並べ替え（SortableJS）は #groupList に 1 回付ければ、描き直しても効き続ける
        if (!groupOrderAttached) {
          groupOrderAttached = true;
          GroupOrder.attach($('groupList'), saveGroupOrder);
        }
"""),
("""  var myGroups = {};          // { code: { joinedAt, order? } }
""",
"""  var myGroups = {};          // { code: { joinedAt, order? } }
  var groupOrderAttached = false;   // サイドバーの並べ替えを付けたか（1 回だけ）
"""),
]

CSS = [
(""".group-item-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
""",
""".group-item-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }

/* 工事5: 並べ替えのつまみ（行の右端。ここだけでドラッグする）*/
.group-item { display: flex; align-items: center; }
.group-item-handle {
  flex-shrink: 0;
  align-self: stretch;
  width: 28px;
  /* 行の上下と右の padding（11px 16px）を打ち消して、行いっぱいの高さにする */
  margin: -11px -16px -11px 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-300);
  font-size: 0.8rem;
  letter-spacing: -0.2em;
  cursor: grab;
  touch-action: none;           /* これが無いと iOS で指を動かした瞬間にスクロールに取られる */
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.group-item-handle:hover { color: var(--gray-500); }
.group-item-handle:active { cursor: grabbing; }
.group-item-ghost { opacity: 0.4; }
"""),
]

HTML = [
("""<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>
""",
"""<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>
"""),
("""<script src="js/store.js"></script>
""",
"""<script src="js/store.js"></script>
<script src="js/group_order.js"></script>
"""),
]

MAKE_UITEST = [
("""    '<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>\\n',
""",
"""    '<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>\\n',
    # 工事5: SortableJS も外す（CDN が読めないときに一覧が今までどおり動くことを確かめる）
    '<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>\\n',
"""),
]

TARGETS = [
    (os.path.join(ROOT, "js", "ui.js"), UI, "GroupOrder.sortCodes"),
    (os.path.join(ROOT, "css", "v2.css"), CSS, ".group-item-handle"),
    (os.path.join(ROOT, "index.html"), HTML, "js/group_order.js"),
    (os.path.join(ROOT, "tools", "make_uitest.py"), MAKE_UITEST, "sortablejs"),
]


def plan(path, edits, marker):
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if marker in src:
        return None, ["すでに適用済み: " + path]
    errors = []
    out = src
    # 順に当てる（前の置換の結果に対して次を数える）
    for before, after in edits:
        n = out.count(fix(before))
        if n != 1:
            errors.append("%s: 置換対象の一致が %d 件（1 件であるべき）: %s"
                          % (os.path.basename(path), n, before.strip().splitlines()[0]))
            continue
        out = out.replace(fix(before), fix(after), 1)
    return out, errors


def main():
    outs = []
    errors = []
    for path, edits, marker in TARGETS:
        out, errs = plan(path, edits, marker)
        errors.extend(errs)
        outs.append((path, out))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    for path, out in outs:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print("書き込み完了: " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
