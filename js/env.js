/*
 * env.js — 実行環境の判定（工事4a）
 *
 * ブラウザ: <script src="js/env.js"> で window.Env
 * Node    : require('./js/env.js')
 *
 * いまのところ「アプリ内ブラウザかどうか」だけ。
 * LINE や Discord の中のブラウザでは Google ログインが拒否されるため、
 * ログイン画面で「Safari / Chrome で開いてください」と案内する（§5.1）。
 * 誤判定でログインできなくなると困るので、**ログインボタン自体は残す**こと。
 */
(function (root) {
  'use strict';

  /**
   * アプリ内ブラウザ（WebView）らしいかどうか。
   * 確実な判定方法は無いので、よくあるアプリの UA を拾う。
   * @param {string} ua navigator.userAgent
   * @returns {boolean}
   */
  function isInAppBrowser(ua) {
    var s = (ua == null) ? '' : String(ua);
    if (!s) return false;

    // アプリ名がそのまま入るもの
    if (/\bLine\//i.test(s)) return true;          // LINE
    if (/Discord/i.test(s)) return true;           // Discord
    if (/\bFBAN\/|\bFBAV\//.test(s)) return true;  // Facebook / Messenger
    if (/Instagram/i.test(s)) return true;         // Instagram
    if (/\bTwitter\b/i.test(s)) return true;       // X（Twitter）
    if (/MicroMessenger/i.test(s)) return true;    // WeChat

    // Android の WebView は UA に「; wv)」が入る
    if (/;\s*wv\)/.test(s)) return true;

    // iOS の WKWebView は Safari/ を名乗らない（Mobile/ はあるのに Safari/ が無い）
    if (/Mobile\//.test(s) && !/Safari\//.test(s)) return true;

    return false;
  }

  var api = { isInAppBrowser: isInAppBrowser };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Env = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
