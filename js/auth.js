/*
 * auth.js — Google ログイン / ログアウト / ログイン状態の監視
 *
 * 画面の出し分けは ui.js（KKAuth.onChange のコールバック）で行う。
 * ここは Firebase Authentication とのやりとりだけを持つ。
 */
(function (root) {
  'use strict';

  var FB = root.KKFirebase;
  var handlers = [];
  var currentUser = null;

  function provider() {
    var p = new firebase.auth.GoogleAuthProvider();
    // 複数アカウントを持っている人が毎回選べるように
    p.setCustomParameters({ prompt: 'select_account' });
    return p;
  }

  /**
   * ログイン。まず signInWithPopup、だめなら signInWithRedirect。
   * ポップアップが拒否される環境（モバイル・アプリ内ブラウザ）向けのフォールバック。
   * @returns {Promise}
   */
  function login() {
    if (!FB || !FB.ready) {
      return Promise.reject(new Error('Firebase が初期化できていません'));
    }
    return FB.auth.signInWithPopup(provider()).catch(function (err) {
      var code = err && err.code ? err.code : '';
      var popupFailed =
        code === 'auth/popup-blocked' ||
        code === 'auth/popup-closed-by-user' ||
        code === 'auth/cancelled-popup-request' ||
        code === 'auth/operation-not-supported-in-this-environment' ||
        code === 'auth/web-storage-unsupported';
      if (popupFailed) {
        return FB.auth.signInWithRedirect(provider());
      }
      throw err;
    });
  }

  function logout() {
    if (!FB || !FB.ready) return Promise.resolve();
    return FB.auth.signOut();
  }

  /** ログイン状態が変わるたびに呼ばれるコールバックを登録する（引数は user または null） */
  function onChange(fn) {
    handlers.push(fn);
    if (currentUser !== null) fn(currentUser);
  }

  function user() { return currentUser; }

  if (FB && FB.ready) {
    // リダイレクト方式で戻ってきたときのエラーを拾う
    FB.auth.getRedirectResult().catch(function (err) {
      if (root.KKUI && root.KKUI.toast) {
        root.KKUI.toast('ログインに失敗しました: ' + (err && err.message ? err.message : err), 'error');
      }
    });

    FB.auth.onAuthStateChanged(function (u) {
      currentUser = u || null;
      handlers.forEach(function (fn) {
        try { fn(currentUser); } catch (e) { console.error(e); }
      });
    });
  }

  root.KKAuth = {
    login: login,
    logout: logout,
    onChange: onChange,
    user: user
  };
})(window);
