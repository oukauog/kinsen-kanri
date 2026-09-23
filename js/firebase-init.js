/*
 * firebase-init.js — Firebase の初期化だけを持つ
 *
 * SDK 本体（compat 版）の <script> は index.html 側で gstatic から読み込む。
 * このファイルはその後ろで読み込まれる前提。
 *
 * ここの設定値はクライアントに公開される前提のもの（Firebase の仕様上、
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
 */
(function (root) {
  'use strict';

  // プロキシが無い環境（localhost 等）で使う、従来からの authDomain
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
    return /\.vercel\.app$/i.test(h) ? h : FALLBACK_AUTH_DOMAIN;
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
    authDomain: authDomain,
    databaseURL: "https://kinsen-kanri-default-rtdb.firebaseio.com",
    projectId: "kinsen-kanri",
    storageBucket: "kinsen-kanri.firebasestorage.app",
    messagingSenderId: "808766408416",
    appId: "1:808766408416:web:6166c7a8134ce4e3f43285"
  };

  if (typeof firebase === 'undefined') {
    // CDN が落ちている・ブロックされている等
    root.KKFirebase = { ready: false, error: 'Firebase SDK が読み込めませんでした' };
    return;
  }

  firebase.initializeApp(firebaseConfig);

  // 検収でどちらの経路を使ったか分かるように 1 行だけ出す
  console.log('[kinsen-kanri] authDomain = ' + authDomain +
    (authDomain === FALLBACK_AUTH_DOMAIN ? '（従来どおり）' : '（自分のドメインでプロキシ）'));

  root.KKFirebase = {
    ready: true,
    error: null,
    authDomain: authDomain,
    app: firebase.app(),
    auth: firebase.auth(),
    db: firebase.database(),
    // サーバ時刻。createdAt / updatedAt に使う
    now: function () { return firebase.database.ServerValue.TIMESTAMP; }
  };
})(typeof window !== 'undefined' ? window : globalThis);
