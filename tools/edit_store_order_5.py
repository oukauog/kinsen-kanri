# -*- coding: utf-8 -*-
"""
工事5: js/store.js にグループの並び順（users/{uid}/groups/{code}/order）を足す。

  ・冒頭のデータモデルのコメントを { joinedAt, order? } に直し、並び順の決めごとを足す
  ・createGroup(name, memberNames, order) / joinGroup(code, order):
    order を引数で受け取り、joinedAt と一緒に set する
    （order が数値でなければ書かない＝今までどおり { joinedAt } だけ）
  ・setGroupOrder(codes): users/{uid}/groups への 1 回の update で
    '<code>/order' = 0, 1, 2, … を書く。joinedAt には触れない。wrapWrite で包む
  ・migrateRoom（旧データの移行）は触らない

groups/{code} 側には何も書かない。Firebase のセキュリティルールは変更しない
（users/$uid は本人だけが読み書きでき、中身の検証は無い）。

置換対象の一致が「ちょうど 1 つ」であることを確認してから書き戻す。
実行: py -X utf8 tools/edit_store_order_5.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "store.js")

EDITS = [
# ① データモデルのコメント
(""" *   users/{uid}/groups/{code}      : { joinedAt }            ← 左サイドバーの元
""",
""" *   users/{uid}/groups/{code}      : { joinedAt, order? }    ← 左サイドバーの元
"""),
(""" * ※ 名前つきの項目（…Name）は工事4b から。""",
""" * ※ order（サイドバーの並び順、工事5）は本人だけの好み。表示順のキーは
 *   「order が数値なら order、無ければ joinedAt（それも無ければ 0）」の昇順、同点はコード順
 *   （js/group_order.js）。新規作成・コード参加は「今の表示順キーの最大 + 1」で一番下に入る。
 *   ドラッグ＆ドロップで並べ替えたら、その順で 0..n-1 を書き直す（setGroupOrder）。
 *   order の無い既存グループはバックフィルしない。groups/{code} 側には書かない。ルールは変更なし
 *
 * ※ 名前つきの項目（…Name）は工事4b から。"""),
# ② watchMyGroups の説明
("""   * users/{uid}/groups を監視する。cb には { code: {joinedAt} } が渡る。""",
"""   * users/{uid}/groups を監視する。cb には { code: {joinedAt, order?} } が渡る。"""),
# ③ createGroup
("""   * @param {string[]} memberNames メンバー名（2 人以上）
   * @returns {Promise<string>} 共有コード
   */
  function createGroup(name, memberNames) {""",
"""   * @param {string[]} memberNames メンバー名（2 人以上）
   * @param {number} [order] サイドバーの並び順（ui.js が KKGroupOrder.nextOrder で決める）
   * @returns {Promise<string>} 共有コード
   */
  function createGroup(name, memberNames, order) {"""),
("""        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () {""",
"""        ref('users/' + myUid + '/groups/' + code).set(myGroupEntry(order))
        .then(function () {"""),
# ④ joinGroup
("""   * 共有コードで参加する。meta が無ければ何もせずエラー。
   * @returns {Promise<Object>} meta
   */
  function joinGroup(code) {""",
"""   * 共有コードで参加する。meta が無ければ何もせずエラー。
   * @param {number} [order] サイドバーの並び順（ui.js が KKGroupOrder.nextOrder で決める）
   * @returns {Promise<Object>} meta
   */
  function joinGroup(code, order) {"""),
("""        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() }))
        .then(function () { return meta; });""",
"""        ref('users/' + myUid + '/groups/' + code).set(myGroupEntry(order)))
        .then(function () { return meta; });"""),
# ⑤ leaveGroup の前に myGroupEntry と setGroupOrder を足す
("""  /** 自分の一覧から外すだけ。グループのデータは残る */
  function leaveGroup(code) {""",
"""  /** users/{uid}/groups/{code} に書く中身。order は数値のときだけ入れる */
  function myGroupEntry(order) {
    var entry = { joinedAt: FB.now() };
    if (typeof order === 'number' && isFinite(order)) entry.order = order;
    return entry;
  }

  /**
   * サイドバーの並び順を書く（ドラッグ＆ドロップで並びが確定したとき）。
   * codes の順に order = 0, 1, 2, … を、users/{uid}/groups への 1 回の update で書く。
   * joinedAt には触れない。groups/{code} 側には何も書かない。
   * @param {string[]} codes 表示順のコード
   */
  function setGroupOrder(codes) {
    var patch = {};
    (codes || []).forEach(function (code, i) { patch[code + '/order'] = i; });
    if (Object.keys(patch).length === 0) return Promise.resolve();
    return wrapWrite('グループの並び順を保存できませんでした',
      ref('users/' + uid() + '/groups').update(patch));
  }

  /** 自分の一覧から外すだけ。グループのデータは残る */
  function leaveGroup(code) {"""),
# ⑥ 公開
("""    joinGroup: joinGroup,
    leaveGroup: leaveGroup,""",
"""    joinGroup: joinGroup,
    setGroupOrder: setGroupOrder,
    leaveGroup: leaveGroup,"""),
]


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "function setGroupOrder" in src:
        print("すでに適用済みです。何もしません。")
        return 0
    errors = []
    for before, _ in EDITS:
        n = src.count(fix(before))
        if n != 1:
            errors.append("置換対象の一致が %d 件（1 件であるべき）: %s" % (n, before.strip().splitlines()[0]))
    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1
    out = src
    for before, after in EDITS:
        out = out.replace(fix(before), fix(after), 1)
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
