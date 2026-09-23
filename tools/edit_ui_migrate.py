# -*- coding: utf-8 -*-
"""
工事2: js/ui.js に
  ① 旧バージョンからの取り込み（コードで参加したときの分岐・選択・結果）
  ② オフラインの帯（§5.7）
  ③ 書き込み失敗のトーストを 1 か所に集約（store.js の onWriteError を受ける）
  ④ 認証切れ（onAuthStateChanged が null）で監視を解除
を足す。

置換対象の一致が「ちょうど 1 つ」であることを全件確認してから書き戻す。
実行: py -X utf8 tools/edit_ui_migrate.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "js", "ui.js")

REPLACEMENTS = []

# ① Migrate を掴む
REPLACEMENTS.append((
    "Migrate を参照する",
    """  var Calc = root.Calc;
  var Store = root.KKStore;
  var Auth = root.KKAuth;""",
    """  var Calc = root.Calc;
  var Store = root.KKStore;
  var Auth = root.KKAuth;
  var Migrate = root.Migrate;"""))

# ② エラーメッセージの組み立てを 1 か所に。store.js が通知済みのものは二重に出さない
REPLACEMENTS.append((
    "エラー文言の組み立てを共通化し、二重トーストを防ぐ",
    """  /** Firebase の失敗を握りつぶさない（v1 の反省点。仕様書 §0-3、§5.7）*/
  function fail(prefix) {
    return function (err) {
      var msg = err && err.message ? err.message : String(err);
      if (err && err.code === 'PERMISSION_DENIED') {
        msg = 'アクセスが拒否されました（ログインし直すか、共有コードを確認してください）';
      }
      console.error(prefix, err);
      toast(prefix + ': ' + msg, 'error');
    };
  }""",
    """  /** エラーを利用者向けの 1 行にする */
  function errText(err) {
    if (err && (err.code === 'PERMISSION_DENIED' || err.code === 'permission-denied')) {
      return 'アクセスが拒否されました（権限がありません）';
    }
    return err && err.message ? err.message : String(err);
  }

  /**
   * Firebase の失敗を握りつぶさない（v1 の反省点。仕様書 §0-3、§5.7）。
   * store.js の wrapWrite が既にトーストを出したものは、印（__kkReported）で
   * 二重表示を避ける。
   */
  function fail(prefix) {
    return function (err) {
      console.error(prefix, err);
      if (err && err.__kkReported) return;
      toast(prefix + ': ' + errText(err), 'error');
    };
  }"""))

# ③ コードで参加 → 旧ルームの取り込みへ分岐
REPLACEMENTS.append((
    "参加フローに旧ルームの取り込みを足す",
    """    fb.textContent = '確認中…';
    Store.readMeta(code).then(function (meta) {
      if (!meta) { fb.textContent = 'そのコードのグループは見つかりませんでした'; return; }
      if (!confirm('「' + (meta.name || '(名称未設定)') + '」に参加しますか？')) {
        fb.textContent = '';
        return;
      }
      return Store.joinGroup(code).then(function () {
        closeModal('joinGroupModal');
        toast('「' + (meta.name || '') + '」に参加しました');
        selectGroup(code);
      });
    }).catch(function (err) {
      fb.textContent = '';
      fail('参加できませんでした')(err);
    });
  }""",
    """    fb.textContent = '確認中…';
    Store.readMeta(code).then(function (meta) {
      // ① v2 のグループがある → 従来どおりの参加
      if (meta) {
        if (!confirm('「' + (meta.name || '(名称未設定)') + '」に参加しますか？')) {
          fb.textContent = '';
          return;
        }
        return Store.joinGroup(code).then(function () {
          closeModal('joinGroupModal');
          toast('「' + (meta.name || '') + '」に参加しました');
          selectGroup(code);
        });
      }
      // ② 無ければ旧バージョンのルームを 1 回だけ読む（読み取りのみ）
      return Store.readRoom(code).then(function (room) {
        if (!room) { fb.textContent = 'そのコードのグループは見つかりませんでした'; return; }
        startMigration(code, room);
      });
    }).catch(function (err) {
      fb.textContent = '';
      fail('参加できませんでした')(err);
    });
  }

  // ---- 旧バージョンからの取り込み（工事2）------------------------------

  var migrateCtx = null;    // { code, room, summary }

  function skipText(sk) {
    var parts = [];
    if (sk.deletedGroups) parts.push('削除済みのグループ ' + sk.deletedGroups + ' 件');
    if (sk.deletedPayments) parts.push('削除済みの支払い ' + sk.deletedPayments + ' 件');
    if (sk.orphanPayments) parts.push('グループが分からない支払い ' + sk.orphanPayments + ' 件');
    return parts.length ? parts.join('、') + ' は取り込みません。' : '';
  }

  /** 旧ルームが見つかったときの入口。1 件なら確認だけ、2 件以上なら選択ダイアログ */
  function startMigration(code, room) {
    var summary = Migrate.summarizeRoom(room);
    if (summary.groups.length === 0) {
      $('joinFeedback').textContent = 'そのコードには取り込めるグループがありませんでした';
      return;
    }
    migrateCtx = { code: code, room: room, summary: summary };

    if (summary.groups.length === 1) {
      var g = summary.groups[0];
      var msg = '旧バージョンのデータが見つかりました。\\n「' + g.name +
        '」（支払い ' + g.paymentCount + ' 件）を取り込んで参加しますか？';
      var sk = skipText(summary.skipped);
      if (sk) msg += '\\n\\n※ ' + sk;
      if (!confirm(msg)) {
        migrateCtx = null;
        $('joinFeedback').textContent = '';
        return;
      }
      runMigration(g.id);
      return;
    }

    $('migrateContent').innerHTML =
      '<p class="migrate-note">このコードには複数のグループがあります。' +
      'コード <strong>' + esc(code) + '</strong> を引き継ぐグループを 1 つ選んでください' +
      '（他のグループには新しいコードを発行します）。</p>' +
      '<div class="migrate-pick-list">' +
      summary.groups.map(function (g, i) {
        return '<label class="migrate-pick">' +
          '<input type="radio" name="migratePick" value="' + esc(g.id) + '"' +
          (i === 0 ? ' checked' : '') + '>' +
          '<span><span class="migrate-pick-name">' + esc(g.name) + '</span>' +
          '<span class="migrate-pick-sub">メンバー ' + g.memberCount + ' 人 ・ 支払い ' +
          g.paymentCount + ' 件</span></span></label>';
      }).join('') + '</div>' +
      (skipText(summary.skipped) ? '<div class="migrate-skip">※ ' +
        esc(skipText(summary.skipped)) + '</div>' : '');

    setMigrateBusy(false);
    closeModal('joinGroupModal');
    openModal('migrateModal');
  }

  function setMigrateBusy(busy) {
    var btn = $('migrateConfirmBtn');
    if (!btn) return;
    btn.disabled = !!busy;
    btn.textContent = busy ? '取り込み中…' : '取り込む';
  }

  function cancelMigrate() {
    migrateCtx = null;
    closeModal('migrateModal');
  }

  function confirmMigrate() {
    var el = document.querySelector('#migrateContent input[name="migratePick"]:checked');
    if (!el) { alert('グループを 1 つ選んでください'); return; }
    runMigration(el.value);
  }

  /** 新しいコードを必要数だけ発行して変換し、書き込む */
  function runMigration(pickGroupId) {
    if (!migrateCtx) return;
    var ctx = migrateCtx;
    var need = Math.max(0, ctx.summary.groups.length - 1);
    var me = Auth.user();
    setMigrateBusy(true);
    $('joinFeedback').textContent = '取り込み中…';

    Store.allocCodes(need).then(function (newCodes) {
      var conv = Migrate.convertRoom(ctx.room, {
        code: ctx.code,
        uid: me ? me.uid : '',
        pickGroupId: pickGroupId,
        newCodes: newCodes,
        now: Date.now()
      });
      return Store.migrateRoom(conv).then(function (res) {
        showMigrateResult(ctx, conv, res);
      });
    }).catch(function (err) {
      setMigrateBusy(false);
      $('joinFeedback').textContent = '';
      fail('取り込みに失敗しました')(err);
    });
  }

  function showMigrateResult(ctx, conv, res) {
    var already = res && res.already ? res.already : [];
    $('migrateResultContent').innerHTML =
      '<p class="migrate-note">旧バージョンのデータを取り込みました。' +
      '新しいコードは、いっしょに使う人に渡してください。</p>' +
      '<div class="migrate-result-list">' +
      conv.order.map(function (code) {
        var g = conv.groups[code];
        var tag = already.indexOf(code) >= 0
          ? '<span class="migrate-result-tag">（すでに取り込み済みでした。参加のみ）</span>' : '';
        return '<div class="migrate-result-item">' +
          '<div class="migrate-result-name">' + esc(g.meta.name) + tag + '</div>' +
          '<span class="migrate-result-code" onclick="copyCode(\\'' + code + '\\')" ' +
          'title="タップでコピー">' + code + '</span>' +
          '<div class="migrate-pick-sub">メンバー ' + Object.keys(g.members || {}).length +
          ' 人 ・ 支払い ' + Object.keys(g.payments || {}).length + ' 件</div>' +
          '</div>';
      }).join('') + '</div>' +
      (skipText(ctx.summary.skipped) ? '<div class="migrate-skip">※ ' +
        esc(skipText(ctx.summary.skipped)) + '</div>' : '');

    setMigrateBusy(false);
    $('joinFeedback').textContent = '';
    closeModal('migrateModal');
    closeModal('joinGroupModal');
    openModal('migrateResultModal');
  }

  function closeMigrateResult() {
    closeModal('migrateResultModal');
    var code = migrateCtx ? migrateCtx.code : null;
    migrateCtx = null;
    if (code) selectGroup(code);
  }

  /** 共有コードをクリップボードへ */
  function copyCode(code) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(function () {
        toast('コードをコピーしました: ' + code);
      }, function () {
        toast('コピーできませんでした（手で選択してください）', 'error');
      });
    } else {
      toast('この端末では自動コピーができません。コードを手で選択してください', 'error');
    }
  }"""))

# ④ オフラインの帯
REPLACEMENTS.append((
    "オフラインの帯を出し入れする",
    """  function setConnected(ok) {
    var dot = $('connDot');
    if (!dot) return;
    dot.classList.toggle('off', !ok);
    dot.title = ok ? 'オンライン（同期中）' : 'オフライン（再接続を待っています）';
  }""",
    """  function setConnected(ok) {
    var dot = $('connDot');
    if (dot) {
      dot.classList.toggle('off', !ok);
      dot.title = ok ? 'オンライン（同期中）' : 'オフライン（再接続を待っています）';
    }
    // 画面上部の細い帯（§5.7）。書いた内容は SDK が再接続時に送る
    var banner = $('offlineBanner');
    if (banner) banner.hidden = !!ok;
  }"""))

# ⑤ 認証が切れたら監視を解除する
REPLACEMENTS.append((
    "認証切れで監視を解除する",
    """      if (!user) {
        showLoggedOut();
        myGroups = {}; metas = {};""",
    """      if (!user) {
        // 認証切れ（期限切れ・別端末でのログアウト）でもここに来る。
        // 監視を残すと権限エラーが出続けるので、必ず外す
        Store.stopWatchMyGroups();
        Store.stopWatchGroup();
        showLoggedOut();
        migrateCtx = null;
        closeModal('migrateModal');
        closeModal('migrateResultModal');
        myGroups = {}; metas = {};"""))

# ⑥ 書き込み失敗のトーストを store.js から受ける
REPLACEMENTS.append((
    "書き込み失敗のトーストを登録する",
    """    Store.watchConnection(setConnected);""",
    """    // 書き込みの失敗は、どこから呼ばれたものでも必ずここでトーストになる（§5.7）
    Store.onWriteError(function (op, err) {
      toast(op + ': ' + errText(err), 'error');
    });

    Store.watchConnection(setConnected);"""))

# ⑦ global に出す
REPLACEMENTS.append((
    "取り込みまわりを global に出す",
    """  root.openJoinModal = openJoinModal;
  root.doJoin = doJoin;""",
    """  root.openJoinModal = openJoinModal;
  root.doJoin = doJoin;
  root.confirmMigrate = confirmMigrate;
  root.cancelMigrate = cancelMigrate;
  root.closeMigrateResult = closeMigrateResult;
  root.copyCode = copyCode;"""))


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

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
