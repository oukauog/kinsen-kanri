/*
 * firebase-init.js — Firebase の初期化だけを持つ
 *
 * SDK 本体（compat 版）の <script> は index.html 側で gstatic から読み込む。
 * このファイルはその後ろで読み込まれる前提。
 *
 * ここの設定値はクライアントに公開される前提のもの（Firebase の仕様上、
 * ウェブアプリの firebaseConfig は秘密ではない）。アクセス制御は
 * Authentication と Realtime Database のセキュリティルールで行う。
 */
(function (root) {
  'use strict';

  var firebaseConfig = {
    apiKey: "AIzaSyAM-ar7pSn0jAaL1fxaCGrA1c1aqIYN3Ak",
    authDomain: "kinsen-kanri.firebaseapp.com",
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

  root.KKFirebase = {
    ready: true,
    error: null,
    app: firebase.app(),
    auth: firebase.auth(),
    db: firebase.database(),
    // サーバ時刻。createdAt / updatedAt に使う
    now: function () { return firebase.database.ServerValue.TIMESTAMP; }
  };
})(window);
