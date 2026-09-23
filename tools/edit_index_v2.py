# -*- coding: utf-8 -*-
"""
工事1: index.html を v2 の器に作り替える。

方針（CLAUDE.md B-1/B-3）:
  ・置換対象の一致が「ちょうど 1 つ」であることを全件検証してから書き戻す
  ・1 つでも一致数が違えば、何も書かずに終了する（部分適用しない）
  ・日本語は UTF-8 のまま書く（数値実体参照にしない）
  ・改行コードは元ファイルのものを保つ

実行: python tools/edit_index_v2.py
"""

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "index.html")

# ---------------------------------------------------------------- 置換定義
# (説明, 置換前, 置換後) を上から順に適用する。改行は \n で書き、
# 実ファイルの改行コードに合わせて後で変換する。

REPLACEMENTS = []

# ① css/v2.css の読み込み
REPLACEMENTS.append((
    "css/v2.css の <link> を追加",
    """  </style>
</head>""",
    """  </style>
  <link rel="stylesheet" href="css/v2.css">
</head>""",
))

# ② ヘッダ右: 旧「☁ 設定」バッジ（v1 の同期設定）を撤去し、
#    表示名・アイコン・ログアウト・接続状態インジケータに置き換える
REPLACEMENTS.append((
    "ヘッダの同期バッジをユーザー欄に差し替え",
    """  <div class="sync-bar" id="syncBar">
    <div class="sync-dot off" id="syncDot"></div>
    <span id="syncLabel" style="opacity:0.7">&#x540C;&#x671F;&#x306A;&#x3057;</span>
    <span class="sync-code-badge" id="syncCodeBadge" onclick="openSyncModal()" title="&#x540C;&#x671F;&#x8A2D;&#x5B9A;">&#x2601; &#x8A2D;&#x5B9A;</span>
  </div>""",
    """  <div class="user-bar" id="userBar" hidden>
    <span class="conn-dot" id="connDot" title="接続状態"></span>
    <img class="user-avatar" id="userAvatar" alt="" hidden>
    <span class="user-name" id="userName"></span>
    <button class="btn-logout" onclick="doLogout()">ログアウト</button>
  </div>""",
))

# ③ ログイン画面を追加し、アプリ本体（.layout）はログイン後だけ表示する
REPLACEMENTS.append((
    "ログイン画面の追加と .layout の出し分け",
    """<div class="layout">""",
    """<div class="login-screen" id="loginScreen" hidden>
  <div class="login-card">
    <div class="login-icon">&#x1F4B0;</div>
    <div class="login-title">金銭管理ツール</div>
    <p class="login-desc">グループの立て替えを記録して、<br>誰が誰にいくら渡せばよいかを計算します。<br>まず Google でログインしてください。</p>
    <button class="btn-google" id="btnLogin" onclick="doLogin()">Google でログイン</button>
    <p class="login-note">Discord や LINE のアプリ内ブラウザではログインできないことがあります。その場合は Safari または Chrome で開いてください。</p>
    <div class="login-error" id="loginError" hidden></div>
  </div>
</div>

<div class="layout" id="appLayout" hidden>""",
))

# ④ サイドバー: 「コードで参加」を追加
REPLACEMENTS.append((
    "サイドバーに「コードで参加」を追加",
    """    <button class="btn-add-group" onclick="openNewGroupModal()">&#xFF0B; &#x30B0;&#x30EB;&#x30FC;&#x30D7;&#x3092;&#x4F5C;&#x6210;</button>""",
    """    <div class="sidebar-btns">
      <button class="btn-add-group" onclick="openNewGroupModal()">&#xFF0B; グループを作成</button>
      <button class="btn-join-group" onclick="openJoinModal()">コードで参加</button>
    </div>""",
))

# ⑤ グループ設定モーダル: 共有コードの表示と「退出」を追加
REPLACEMENTS.append((
    "グループ設定に共有コードと退出を追加",
    """    <div class="modal-footer">
      <div class="modal-footer-left">
        <button class="btn btn-danger btn-sm" onclick="deleteGroup()">&#x30B0;&#x30EB;&#x30FC;&#x30D7;&#x3092;&#x524A;&#x9664;</button>
      </div>""",
    """    <div class="form-group">
      <label class="form-label">共有コード（タップでコピー）</label>
      <div class="share-code-box" id="shareCodeBox" onclick="copyShareCode()"></div>
      <div class="share-code-hint">このコードを渡すと、相手は「コードで参加」からこのグループに入れます</div>
    </div>
    <div class="modal-footer">
      <div class="modal-footer-left">
        <button class="btn btn-secondary btn-sm" onclick="leaveGroup()">退出</button>
        <button class="btn btn-danger btn-sm" onclick="deleteGroup()">&#x30B0;&#x30EB;&#x30FC;&#x30D7;&#x3092;&#x524A;&#x9664;</button>
      </div>""",
))

# ⑥ v1 の同期設定モーダルを撤去し、「コードで参加」モーダルに置き換える
REPLACEMENTS.append((
    "同期設定モーダルを「コードで参加」モーダルに差し替え",
    """<!-- Modal: 同期設定 -->
<div class="modal-overlay" id="syncModal">
  <div class="modal">
    <div class="modal-title">&#x2601; &#x540C;&#x671F;&#x8A2D;&#x5B9A;</div>
    <div id="syncModalContent"></div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('syncModal')">&#x9589;&#x3058;&#x308B;</button>
    </div>
  </div>
</div>""",
    """<!-- Modal: コードで参加 -->
<div class="modal-overlay" id="joinGroupModal">
  <div class="modal">
    <div class="modal-title">&#x1F517; コードで参加</div>
    <div class="form-group">
      <label class="form-label">共有コード（6桁）</label>
      <input type="text" class="form-input" id="joinCodeInput" placeholder="例: ABC123" autocomplete="off" autocapitalize="characters" spellcheck="false" onkeydown="if(event.key==='Enter')doJoin()">
      <div class="join-feedback" id="joinFeedback"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('joinGroupModal')">キャンセル</button>
      <button class="btn btn-primary" onclick="doJoin()">参加する</button>
    </div>
  </div>
</div>""",
))


# ⑦ v1 のインライン <script> を丸ごと撤去し、外部スクリプトの読み込みに置き換える
#    （開始行と終了行の両方が 1 つだけであることを確認してから切り出す）
INLINE_SCRIPT_HEAD = (
    "<script>\n"
    "var db = { groups: [], payments: [], deletedGroupIds: [], deletedPaymentIds: [] };"
)
INLINE_SCRIPT_TAIL = "render();\n</script>"

NEW_SCRIPTS = """<!-- Firebase SDK（compat 版）-->
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>

<!-- v2 本体（読み込み順に意味がある: 初期化 → 計算 → 保存 → 認証 → 画面）-->
<script src="js/firebase-init.js"></script>
<script src="js/calc.js"></script>
<script src="js/store.js"></script>
<script src="js/auth.js"></script>
<script src="js/ui.js"></script>"""


def to_nl(text, nl):
    return text.replace("\n", nl) if nl != "\n" else text


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()

    nl = "\r\n" if "\r\n" in src else "\n"
    print("改行コード: " + ("CRLF" if nl == "\r\n" else "LF"))

    errors = []
    plan = []

    for label, before, after in REPLACEMENTS:
        b = to_nl(before, nl)
        n = src.count(b)
        if n != 1:
            errors.append("%s: 一致 %d 件（1 件であるべき）" % (label, n))
        plan.append((label, b, to_nl(after, nl)))

    head = to_nl(INLINE_SCRIPT_HEAD, nl)
    tail = to_nl(INLINE_SCRIPT_TAIL, nl)
    nh, nt = src.count(head), src.count(tail)
    if nh != 1:
        errors.append("インライン script の開始: 一致 %d 件（1 件であるべき）" % nh)
    if nt != 1:
        errors.append("インライン script の終了: 一致 %d 件（1 件であるべき）" % nt)

    if errors:
        print("中止しました。ファイルは変更していません:")
        for e in errors:
            print("  - " + e)
        return 1

    out = src
    for label, b, a in plan:
        out = out.replace(b, a, 1)
        print("置換しました: " + label)

    s = out.index(head)
    e = out.index(tail, s) + len(tail)
    out = out[:s] + to_nl(NEW_SCRIPTS, nl) + out[e:]
    print("置換しました: v1 インライン script を外部スクリプトの読み込みに差し替え")

    # 念のための健全性チェック
    assert out.count("<script") == 8, "script タグの数が想定外: %d" % out.count("<script")
    assert "</body>" in out and "</html>" in out
    assert "openSyncModal" not in out, "v1 の同期設定への参照が残っている"

    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("書き込み完了: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
