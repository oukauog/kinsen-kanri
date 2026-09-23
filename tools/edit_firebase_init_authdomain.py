# -*- coding: utf-8 -*-
"""
工事1-2: js/firebase-init.js の authDomain を「アプリ自身のホスト」に切り替える。

理由:
  iPhone Safari で signInWithRedirect が
  "Unable to process request due to missing initial state." で止まる。
  アプリの配信元（*.vercel.app）と authDomain（kinsen-kanri.firebaseapp.com）が
  別サイトのため、Safari のストレージ分離で認証の途中状態が引き継げない。
  Firebase 公式の Option 3（自分のドメインで /__/auth/* を受けて firebaseapp.com へ
  プロキシする）に合わせる。プロキシ設定は vercel.json の rewrites。

やること:
  ・authDomain を決める純粋関数 pickAuthDomain() を足す（Node からテストできるように
    module.exports も生やす。ブラウザでは従来どおり window.KKFirebase）
  ・*.vercel.app なら location.hostname、それ以外（localhost 等）は従来の値
  ・どちらを使ったかを KKFirebase.authDomain に載せ、コンソールに 1 行出す

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
1 つでも違えば何も書かずに終了する。

実行: py -X utf8 tools/edit_firebase_init_authdomain.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "firebase-init.js")

REPLACEMENTS = []

# ① 見出しコメントに経緯を足す
REPLACEMENTS.append((
    "冒頭コメントに authDomain の経緯を追記",
    """ * ここの設定値はクライアントに公開される前提のもの（Firebase の仕様上、
 * ウェブアプリの firebaseConfig は秘密ではない）。アクセス制御は
 * Authentication と Realtime Database のセキュリティルールで行う。
 */""",
    """ * ここの設定値はクライアントに公開される前提のもの（Firebase の仕様上、
 * ウェブアプリの firebaseConfig は秘密ではない）。アクセス制御は
 * Authentication と Realtime Database のセキュリティルールで行う。
 *
 * authDomain だけは配信元によって変える（工事1-2）。
 * iPhone Safari は「別サイトのストレージ」を分離するため、authDomain が
 * kinsen-kanri.firebaseapp.com のままだとリダイレクト認証の途中状態が消え、
 * "Unable to process request due to missing initial state." で止まる。
 * *.vercel.app では自分のホストを authDomain にし、/__/auth/* を
 * vercel.json の rewrites で firebaseapp.com へプロキシする
 * （Firebase 公式「signInWithRedirect のベストプラクティス」の Option 3）。
 * 切替の判定は tests/authdomain.test.js で固定してある。
 */"""))

# ② pickAuthDomain を足し、Node から読めるようにする（ブラウザ側は従来どおり）
REPLACEMENTS.append((
    "pickAuthDomain と Node 向けの入口を追加",
    """  var firebaseConfig = {
    apiKey: "AIzaSyAM-ar7pSn0jAaL1fxaCGrA1c1aqIYN3Ak",
    authDomain: "kinsen-kanri.firebaseapp.com",""",
    """  // プロキシが無い環境（localhost 等）で使う、従来からの authDomain
  var FALLBACK_AUTH_DOMAIN = "kinsen-kanri.firebaseapp.com";

  /**
   * 認証を受けるドメインを決める。
   * ・*.vercel.app（本番とプレビュー）→ 自分のホスト。
   *   vercel.json の rewrites が /__/auth/* を firebaseapp.com へ転送するので、
   *   ブラウザから見ると認証もアプリも同じサイトになり、Safari でも状態が消えない
   * ・それ以外（localhost、file: など）→ 従来どおり firebaseapp.com
   * @param {string} hostname location.hostname
   * @returns {string} authDomain に入れる値
   */
  function pickAuthDomain(hostname) {
    var h = String(hostname == null ? '' : hostname);
    return /\\.vercel\\.app$/i.test(h) ? h : FALLBACK_AUTH_DOMAIN;
  }

  // Node（tests/authdomain.test.js）からは判定だけを使う。
  // ブラウザの初期化はここから下には進まない。
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      pickAuthDomain: pickAuthDomain,
      FALLBACK_AUTH_DOMAIN: FALLBACK_AUTH_DOMAIN
    };
    return;
  }

  var authDomain = pickAuthDomain(root.location && root.location.hostname);

  var firebaseConfig = {
    apiKey: "AIzaSyAM-ar7pSn0jAaL1fxaCGrA1c1aqIYN3Ak",
    authDomain: authDomain,"""))

# ③ KKFirebase に authDomain を載せ、どちらを使ったかを 1 行出す
REPLACEMENTS.append((
    "KKFirebase に authDomain を公開し、コンソールに 1 行出す",
    """  firebase.initializeApp(firebaseConfig);

  root.KKFirebase = {
    ready: true,
    error: null,""",
    """  firebase.initializeApp(firebaseConfig);

  // 検収でどちらの経路を使ったか分かるように 1 行だけ出す
  console.log('[kinsen-kanri] authDomain = ' + authDomain +
    (authDomain === FALLBACK_AUTH_DOMAIN ? '（従来どおり）' : '（自分のドメインでプロキシ）'));

  root.KKFirebase = {
    ready: true,
    error: null,
    authDomain: authDomain,"""))

# ④ Node でも読めるように IIFE の引数を直す
REPLACEMENTS.append((
    "IIFE の引数を window 決め打ちから直す",
    """})(window);""",
    """})(typeof window !== 'undefined' ? window : globalThis);"""))


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

    # 念のため
    assert out.count('apiKey: "AIzaSyAM-ar7pSn0jAaL1fxaCGrA1c1aqIYN3Ak"') == 1
    assert out.count('databaseURL: "https://kinsen-kanri-default-rtdb.firebaseio.com"') == 1
    assert out.count('appId: "1:808766408416:web:6166c7a8134ce4e3f43285"') == 1

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
