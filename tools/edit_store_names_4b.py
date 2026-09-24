# -*- coding: utf-8 -*-
"""
工事4b-B: js/store.js の書き込みに「表示名」を一緒に保存する。

なぜ名前も保存するか:
  uid から名前を引くには他人の users/{uid}/profile を読む必要があるが、
  セキュリティルールでは本人しか読めない。so 書いた時点の表示名を
  そのレコードに残す（あとで名前を変えても当時の名前が残るのは、
  工事3 の transfers.fromName / toName と同じ考え方）。

足すもの:
  ・currentUserName()       表示名を決める 1 か所（displayName → email の @ 前 → 「（名前なし）」）
  ・addPayment              createdByName
  ・updatePayment           updatedBy（uid）と updatedByName ※表示は工事4b ではしない。保存だけ
  ・confirmSettlement       createdByName（settle.js には触らず、書き込む直前に足す）
  ・setTransferDone         doneByName（外すときは doneBy / doneAt と同じく null）

既存データの読み替え・一括更新（バックフィル）はしない。
項目が無い古いレコードは「無いもの」として扱う（画面で何も出さない）。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_store_names_4b.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "store.js")

REPLACEMENTS = []

# ① 冒頭コメントのデータモデルに名前の項目を書き足す
REPLACEMENTS.append((
    "冒頭コメントに表示名の項目を追記",
    """ *   groups/{code}/payments/{pid}   : { date, memo, payerId, amount,
 *                                      participants:{mid:true}, settlementId, pending,
 *                                      createdBy, createdAt, updatedAt }
 *   groups/{code}/settlements/{sid}: { createdAt, createdBy, paymentIds:{pid:true},
 *                                      transfers/{tid}: { from, to, fromName, toName,
 *                                                         amount, done, doneAt?, doneBy? } }""",
    """ *   groups/{code}/payments/{pid}   : { date, memo, payerId, amount,
 *                                      participants:{mid:true}, settlementId, pending,
 *                                      createdBy, createdByName, createdAt,
 *                                      updatedBy?, updatedByName?, updatedAt }
 *   groups/{code}/settlements/{sid}: { createdAt, createdBy, createdByName,
 *                                      paymentIds:{pid:true},
 *                                      transfers/{tid}: { from, to, fromName, toName,
 *                                                         amount, done, doneAt?, doneBy?,
 *                                                         doneByName? } }
 *
 * ※ 名前つきの項目（…Name）は工事4b から。それ以前のレコードや移行で入ったものには
 *   無い。無いものは「無いまま」扱う（あとから埋める一括更新はしない）"""))

# ② 表示名を決める関数
REPLACEMENTS.append((
    "表示名を決める関数を追加",
    """  function ref(path) { requireReady(); return FB.db.ref(path); }""",
    """  /**
   * いまログインしている人の表示名。
   * displayName → メールの @ より前 → 「（名前なし）」の順で決める。
   * 他人の名前はここでは引かない（ルール上、他人の profile は読めない）。
   */
  function currentUserName() {
    var u = FB && FB.ready ? FB.auth.currentUser : null;
    if (!u) return '（名前なし）';
    var n = (u.displayName || '').trim();
    if (n) return n;
    var mail = (u.email || '').trim();
    if (mail && mail.indexOf('@') > 0) return mail.slice(0, mail.indexOf('@'));
    return '（名前なし）';
  }

  function ref(path) { requireReady(); return FB.db.ref(path); }"""))

# ③ 支払いの新規作成
REPLACEMENTS.append((
    "支払いの新規作成に入力者の名前を足す",
    """      settlementId: null,   // 清算するとここに sid が入る
      pending: pending,     // 金額確認中（残高・清算から外れる）
      createdBy: myUid,
      createdAt: FB.now(),
      updatedAt: FB.now()""",
    """      settlementId: null,   // 清算するとここに sid が入る
      pending: pending,     // 金額確認中（残高・清算から外れる）
      createdBy: myUid,
      createdByName: currentUserName(),   // 書いた時点の表示名（工事4b）
      createdAt: FB.now(),
      updatedAt: FB.now()"""))

# ④ 支払いの更新（保存のみ。表示は工事4b ではしない）
REPLACEMENTS.append((
    "支払いの更新に更新者を足す",
    """          participants: p.participants,
          pending: pending,
          updatedAt: FB.now()
        }));""",
    """          participants: p.participants,
          pending: pending,
          updatedBy: uid(),                   // 誰が直したか（保存のみ。表示は今回しない）
          updatedByName: currentUserName(),
          updatedAt: FB.now()
        }));"""))

# ⑤ 清算の確定（settle.js には触らず、書き込む直前に名前を足す）
REPLACEMENTS.append((
    "清算の確定に確定者の名前を足す",
    """  function confirmSettlement(code, settlement) {
    var sid = ref('groups/' + code + '/settlements').push().key;
    var updates = {};
    updates['settlements/' + sid] = settlement;""",
    """  function confirmSettlement(code, settlement) {
    var sid = ref('groups/' + code + '/settlements').push().key;
    var updates = {};
    // settle.js（純粋関数）は名前を知らないので、書き込む直前にここで足す
    var rec = {};
    for (var k in settlement) {
      if (Object.prototype.hasOwnProperty.call(settlement, k)) rec[k] = settlement[k];
    }
    rec.createdByName = currentUserName();
    updates['settlements/' + sid] = rec;"""))

# ⑥ 送金チェック
REPLACEMENTS.append((
    "送金チェックにチェックした人の名前を足す",
    """      ref(base).update({
        done: !!done,
        doneAt: done ? FB.now() : null,
        doneBy: done ? myUid : null
      }));""",
    """      ref(base).update({
        done: !!done,
        doneAt: done ? FB.now() : null,
        doneBy: done ? myUid : null,
        doneByName: done ? currentUserName() : null
      }));"""))

# ⑦ 公開（画面から表示名を使えるように）
REPLACEMENTS.append((
    "currentUserName を公開する",
    """  root.KKStore = {
    randomCode: randomCode,""",
    """  root.KKStore = {
    randomCode: randomCode,
    currentUserName: currentUserName,"""))


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
