# -*- coding: utf-8 -*-
"""
工事2: js/store.js に移行まわりと書き込みエラーの拾い上げを足す。

足すもの:
  ・readRoom(code)      旧ルームの読み取り（1 回だけ。書き込みは一切しない）
  ・allocCodes(n)       重複しない新しい共有コードを n 個発行
  ・migrateRoom(conv)   変換済みデータの書き込み。ルールに合わせて
                        「先に users/{uid}/groups/{code} → その後 groups/{code}」の順。
                        meta は transaction で「null のときだけ書く」（二重移行の防止）。
                        途中で失敗したら、自分が足した users 側の登録を取り消す
  ・書き込み（set/update/remove/transaction）を wrapWrite で包み、失敗を必ず
    onWriteError に通す（§5.7「握りつぶさない」）。二重にトーストしないよう、
    拾った err には __kkReported = true を立てる

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_store_migrate.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "store.js")

REPLACEMENTS = []

# ① 冒頭コメントに移行の扱いを書き足す
REPLACEMENTS.append((
    "冒頭コメントに移行の決めごとを追記",
    """ *   ・セキュリティルールの都合上、グループ作成・参加はどちらも
 *     「先に users/{uid}/groups/{code} を書いてから groups/{code} を触る」順序が必須
 */""",
    """ *   ・セキュリティルールの都合上、グループ作成・参加はどちらも
 *     「先に users/{uid}/groups/{code} を書いてから groups/{code} を触る」順序が必須
 *   ・旧パス rooms/{code} は「コードで参加したとき 1 回だけ読む」以外に触らない。
 *     書き込みは禁止（友人の実データ。工事2 の移行でも読むだけ）
 *   ・書き込みは wrapWrite で包み、失敗を必ず onWriteError に通す（§5.7）
 */"""))

# ② エラーの拾い上げ（wrapWrite）を追加
REPLACEMENTS.append((
    "書き込みエラーの拾い上げを追加",
    """  function ref(path) { requireReady(); return FB.db.ref(path); }""",
    """  function ref(path) { requireReady(); return FB.db.ref(path); }

  // ---- 書き込みエラーの拾い上げ（§5.7）--------------------------------

  var writeErrorHandler = null;

  /** 書き込みが失敗したときに呼ばれる関数を登録する（ui.js がトーストを出す） */
  function onWriteError(fn) { writeErrorHandler = fn; }

  /**
   * 書き込みの Promise を包んで、失敗を必ず 1 か所に通す。
   * 呼び出し側の .catch もそのまま動くように、エラーは再送出する。
   * 二重にトーストしないよう、通知済みの印を付ける。
   * @param {string} op 失敗したときに出す日本語の操作名
   */
  function wrapWrite(op, p) {
    return p.catch(function (err) {
      if (err && !err.__kkReported) {
        err.__kkReported = true;
        if (writeErrorHandler) {
          try { writeErrorHandler(op, err); } catch (e) { console.error(e); }
        } else {
          console.error(op, err);
        }
      }
      throw err;
    });
  }"""))

# ③ 既存の書き込みを wrapWrite で包む（1 つずつ、一致 1 件を確認しながら）
REPLACEMENTS.append((
    "saveProfile を包む",
    """    return ref('users/' + user.uid + '/profile').set({
      displayName: user.displayName || '',
      photoURL: user.photoURL || '',
      updatedAt: FB.now()
    });""",
    """    return wrapWrite('プロフィールを保存できませんでした',
      ref('users/' + user.uid + '/profile').set({
        displayName: user.displayName || '',
        photoURL: user.photoURL || '',
        updatedAt: FB.now()
      }));"""))

REPLACEMENTS.append((
    "createGroup を包む",
    """      // ルールが「自分の一覧に入っていること」を要求するので、先に自分を登録する
      return ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () {
          return ref('groups/' + code).update({""",
    """      // ルールが「自分の一覧に入っていること」を要求するので、先に自分を登録する
      return wrapWrite('グループを作成できませんでした',
        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () {
          return ref('groups/' + code).update({"""))

REPLACEMENTS.append((
    "createGroup の閉じ括弧を合わせる",
    """            members: members
          });
        })
        .then(function () { return code; });""",
    """            members: members
          });
        }))
        .then(function () { return code; });"""))

REPLACEMENTS.append((
    "joinGroup を包む",
    """      if (!meta) throw new Error('そのコードのグループは見つかりませんでした');
      return ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() })
        .then(function () { return meta; });""",
    """      if (!meta) throw new Error('そのコードのグループは見つかりませんでした');
      return wrapWrite('グループに参加できませんでした',
        ref('users/' + myUid + '/groups/' + code).set({ joinedAt: FB.now() }))
        .then(function () { return meta; });"""))

REPLACEMENTS.append((
    "leaveGroup を包む",
    """  function leaveGroup(code) {
    return ref('users/' + uid() + '/groups/' + code).remove();
  }""",
    """  function leaveGroup(code) {
    return wrapWrite('退出できませんでした',
      ref('users/' + uid() + '/groups/' + code).remove());
  }"""))

REPLACEMENTS.append((
    "deleteGroup を包む",
    """    return ref('groups/' + code).remove()
      .then(function () { return ref('users/' + myUid + '/groups/' + code).remove(); });""",
    """    return wrapWrite('グループを削除できませんでした',
      ref('groups/' + code).remove()
        .then(function () { return ref('users/' + myUid + '/groups/' + code).remove(); }));"""))

REPLACEMENTS.append((
    "setGroupName を包む",
    """  function setGroupName(code, name) {
    return ref('groups/' + code + '/meta/name').set(name);
  }""",
    """  function setGroupName(code, name) {
    return wrapWrite('グループ名を変更できませんでした',
      ref('groups/' + code + '/meta/name').set(name));
  }"""))

REPLACEMENTS.append((
    "addMember を包む",
    """    return ref('groups/' + code + '/members/' + mid)
      .set({ name: name, order: order })
      .then(function () { return mid; });""",
    """    return wrapWrite('メンバーを追加できませんでした',
      ref('groups/' + code + '/members/' + mid).set({ name: name, order: order }))
      .then(function () { return mid; });"""))

REPLACEMENTS.append((
    "renameMember を包む",
    """  function renameMember(code, mid, name) {
    return ref('groups/' + code + '/members/' + mid + '/name').set(name);
  }""",
    """  function renameMember(code, mid, name) {
    return wrapWrite('メンバー名を変更できませんでした',
      ref('groups/' + code + '/members/' + mid + '/name').set(name));
  }"""))

REPLACEMENTS.append((
    "removeMember を包む",
    """  function removeMember(code, mid) {
    return ref('groups/' + code + '/members/' + mid).remove();
  }""",
    """  function removeMember(code, mid) {
    return wrapWrite('メンバーを削除できませんでした',
      ref('groups/' + code + '/members/' + mid).remove());
  }"""))

REPLACEMENTS.append((
    "addPayment を包む",
    """    var pid = ref('groups/' + code + '/payments').push().key;
    return ref('groups/' + code + '/payments/' + pid).set({""",
    """    var pid = ref('groups/' + code + '/payments').push().key;
    return wrapWrite('支払いを記録できませんでした',
      ref('groups/' + code + '/payments/' + pid).set({"""))

REPLACEMENTS.append((
    "addPayment の閉じ括弧を合わせる",
    """      createdAt: FB.now(),
      updatedAt: FB.now()
    }).then(function () { return pid; });""",
    """      createdAt: FB.now(),
      updatedAt: FB.now()
      })).then(function () { return pid; });"""))

REPLACEMENTS.append((
    "updatePayment を包む",
    """    return ref('groups/' + code + '/payments/' + pid).update({
      date: p.date,
      memo: p.memo || '',
      payerId: p.payerId,
      amount: p.amount,
      participants: p.participants,
      updatedAt: FB.now()
    });""",
    """    return wrapWrite('支払いを更新できませんでした',
      ref('groups/' + code + '/payments/' + pid).update({
        date: p.date,
        memo: p.memo || '',
        payerId: p.payerId,
        amount: p.amount,
        participants: p.participants,
        updatedAt: FB.now()
      }));"""))

REPLACEMENTS.append((
    "removePayment を包む",
    """  function removePayment(code, pid) {
    return ref('groups/' + code + '/payments/' + pid).remove();
  }""",
    """  function removePayment(code, pid) {
    return wrapWrite('支払いを削除できませんでした',
      ref('groups/' + code + '/payments/' + pid).remove());
  }"""))

# ④ 移行まわりの関数を追加（接続状態の節の直前に差し込む）
REPLACEMENTS.append((
    "移行（旧ルームの読み取りと書き込み）を追加",
    """  // ---- 接続状態 -------------------------------------------------------""",
    """  // ---- 移行（旧 rooms からの取り込み。工事2）--------------------------

  /**
   * 旧ルームを 1 回だけ読む。**読み取り専用**。ここでも他のどこでも rooms/ には書かない。
   * @returns {Promise<Object|null>} 旧ルームの中身（無ければ null）
   */
  function readRoom(code) {
    return ref('rooms/' + code).once('value').then(function (s) { return s.val(); });
  }

  /**
   * 重複しない新しい共有コードを n 個発行する（既存の findFreeCode を使う）。
   * @returns {Promise<string[]>}
   */
  function allocCodes(n, acc) {
    var got = acc || [];
    if (got.length >= n) return Promise.resolve(got);
    return findFreeCode().then(function (code) {
      if (got.indexOf(code) >= 0) return allocCodes(n, got);   // まず起きないが念のため
      got.push(code);
      return allocCodes(n, got);
    });
  }

  /**
   * 変換済みデータ（Migrate.convertRoom の戻り値）を書き込む。
   *
   * 手順（ルールの都合でこの順序でないと書けない）:
   *   1. users/{uid}/groups/{code} を登録（自分の一覧に入れる＝グループへの書き込み権限を得る）
   *   2. groups/{code}/meta を transaction で「まだ無いときだけ」書く
   *      → 誰かが先に移行していたら、そのグループは書かずに「参加しただけ」にする
   *   3. meta を書けたグループにだけ members / payments を update で書く
   *
   * 途中で失敗したら、この呼び出しで足した users/{uid}/groups/{code} を取り消して
   * 中途半端な状態を残さない（rooms/ には最初から何も書かない）。
   *
   * @param {Object} converted { groups: { code: {meta, members, payments} }, order: [code] }
   * @returns {Promise<Object>} { migrated: [code], already: [code] }
   *   already = 先に誰かが移行していたので中身は書かなかったコード
   */
  function migrateRoom(converted) {
    var myUid = uid();
    var codes = (converted && converted.order && converted.order.length)
      ? converted.order.slice()
      : Object.keys((converted && converted.groups) || {});
    if (codes.length === 0) return Promise.resolve({ migrated: [], already: [] });

    var addedByMe = [];      // 失敗したときに取り消す対象
    var migrated = [];
    var already = [];

    function rollback() {
      return Promise.all(addedByMe.map(function (code) {
        return ref('users/' + myUid + '/groups/' + code).remove().catch(function () { });
      }));
    }

    // 1. 自分の一覧に登録（もともと入っていたものは取り消し対象にしない）
    function joinAll(i) {
      if (i >= codes.length) return Promise.resolve();
      var code = codes[i];
      var myRef = ref('users/' + myUid + '/groups/' + code);
      return myRef.once('value').then(function (s) {
        if (s.exists()) return null;
        return myRef.set({ joinedAt: FB.now() }).then(function () { addedByMe.push(code); });
      }).then(function () { return joinAll(i + 1); });
    }

    // 2〜3. meta を取り合いしてから中身を書く
    function writeAll(i) {
      if (i >= codes.length) return Promise.resolve();
      var code = codes[i];
      var g = converted.groups[code];
      return ref('groups/' + code + '/meta').transaction(function (current) {
        if (current === null) return g.meta;
        return undefined;      // すでにある → 何もしない（二重移行の防止）
      }).then(function (res) {
        if (!res.committed) { already.push(code); return null; }
        return ref('groups/' + code).update({
          members: g.members || {},
          payments: g.payments || {}
        }).then(function () { migrated.push(code); });
      }).then(function () { return writeAll(i + 1); });
    }

    return wrapWrite('取り込みに失敗しました',
      joinAll(0).then(function () { return writeAll(0); })
        .then(function () { return { migrated: migrated, already: already }; })
        .catch(function (err) {
          return rollback().then(function () { throw err; });
        }));
  }

  // ---- 接続状態 -------------------------------------------------------"""))

# ⑤ 公開
REPLACEMENTS.append((
    "公開する関数に移行まわりを追加",
    """    removePayment: removePayment,
    watchConnection: watchConnection
  };""",
    """    removePayment: removePayment,
    readRoom: readRoom,
    allocCodes: allocCodes,
    migrateRoom: migrateRoom,
    onWriteError: onWriteError,
    watchConnection: watchConnection
  };"""))


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    errors = []
    plan = []
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

    # rooms へ書き込むコードが混ざっていないこと
    import re
    for m in re.finditer(r"ref\('rooms/[^']*'\)\s*\.\s*(\w+)", out):
        assert m.group(1) == "once", "rooms へ once 以外の操作がある: " + m.group(0)

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
