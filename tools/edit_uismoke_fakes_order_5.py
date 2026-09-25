# -*- coding: utf-8 -*-
"""
工事5: tests/ui_smoke_fakes.js の Store を、グループの並び順（order）に対応させる。

  ・createGroup(name, names, order) / joinGroup(code, order) が order を受け取り、
    本物の store.js と同じく「数値のときだけ」 users/{uid}/groups/{code} に { joinedAt, order } を書く
  ・setGroupOrder(codes): 本物と同じく users/{uid}/groups への 1 回の update（キー '<code>/order'）。
    Firebase の複数パス update と同じく、無いノードは作られる
  ・書き込みを _writes に記録する（{ op: 'set' | 'update', path, value }）。通し確認で中身を見るため
  ・_seedMyGroup(code, entry): 自分の一覧に直接 1 件入れる（削除済みグループの行を作る確認用）

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_uismoke_fakes_order_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "tests", "ui_smoke_fakes.js")

EDITS = [
("""  var USER = { uid: 'u-test', displayName: 'テスト太郎', photoURL: '', email: 't@example.com' };
""",
"""  var USER = { uid: 'u-test', displayName: 'テスト太郎', photoURL: '', email: 't@example.com' };
  var writes = [];                // 工事5: users/{uid}/groups への書き込みの記録

  // 本物の store.js の myGroupEntry と同じ: order は数値のときだけ入れる
  function myGroupEntry(order) {
    var entry = { joinedAt: Date.now() };
    if (typeof order === 'number' && isFinite(order)) entry.order = order;
    return entry;
  }
  function setMyGroup(code, order) {
    var entry = myGroupEntry(order);
    data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
    data.users[USER.uid].groups[code] = entry;
    writes.push({ op: 'set', path: 'users/' + USER.uid + '/groups/' + code, value: clone(entry) });
  }
"""),
("""    _data: data,
""",
"""    _data: data,
    _writes: writes,
"""),
("""    createGroup: function (name, names) {""",
"""    createGroup: function (name, names, order) {"""),
("""      data.groups[code] = { meta: { name: name, createdAt: Date.now(), createdBy: USER.uid, schemaVersion: 2 }, members: members };
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      data.users[USER.uid].groups[code] = { joinedAt: Date.now() };
      notifyMyGroups(); notifyGroup(code);""",
"""      data.groups[code] = { meta: { name: name, createdAt: Date.now(), createdBy: USER.uid, schemaVersion: 2 }, members: members };
      setMyGroup(code, order);
      notifyMyGroups(); notifyGroup(code);"""),
("""    joinGroup: function (code) {
      var g = data.groups[code];
      if (!g) return Promise.reject(new Error('見つかりません'));
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      data.users[USER.uid].groups[code] = { joinedAt: Date.now() };
      notifyMyGroups();""",
"""    joinGroup: function (code, order) {
      var g = data.groups[code];
      if (!g) return Promise.reject(new Error('見つかりません'));
      setMyGroup(code, order);
      notifyMyGroups();"""),
("""    leaveGroup: function (code) {""",
"""    // 本物と同じく users/{uid}/groups への 1 回の update（キー '<code>/order'）。joinedAt には触れない
    setGroupOrder: function (codes) {
      var patch = {};
      (codes || []).forEach(function (code, i) { patch[code + '/order'] = i; });
      if (Object.keys(patch).length === 0) return Promise.resolve();
      writes.push({ op: 'update', path: 'users/' + USER.uid + '/groups', value: clone(patch) });
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      var groups = data.users[USER.uid].groups;
      (codes || []).forEach(function (code, i) {
        groups[code] = groups[code] || {};     // Firebase の複数パス update と同じく、無ければ作られる
        groups[code].order = i;
      });
      notifyMyGroups();
      return Promise.resolve();
    },
    _seedMyGroup: function (code, entry) {
      data.users[USER.uid] = data.users[USER.uid] || { groups: {} };
      data.users[USER.uid].groups[code] = clone(entry);
      notifyMyGroups();
    },
    leaveGroup: function (code) {"""),
]


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "setGroupOrder" in src:
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
