# -*- coding: utf-8 -*-
"""
工事4c-2: docs/reports/工事4c_報告.md の末尾に「## 8. 4c-2 修正（日付欄の揃え）」を追記する。
新しいファイルは作らない（依頼どおり既存の報告書に足す）。

末尾が工事4c の §7 の最後の行であることを確認してから追記する。
実行: py -X utf8 tools/append_report_4c2.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "docs", "reports", "工事4c_報告.md")

# 既存の末尾（ここに続けて足す）
TAIL = ("5. **次の候補**（今回は触っていません）: ホーム画面アイコン（`manifest.json` / "
        "`apple-touch-icon`）、xlsx/CSV 取込の復元、2 端末同時の清算確定（工事3 §7-2）、"
        "スマホの見た目細部")

ADDITION = """

---

## 8. 4c-2 修正（日付欄の揃え） — 2026-09-24

工事4c でズームは解消したものの、花井の iPhone 実機で **「支払いを記録」の日付欄（`#payDate`）だけ枠が不自然に伸びて**他の欄と揃わない、という報告を受けての修正です。

- コミット: `b2eb50c`（スマホ幅で入力欄の高さを揃え日付欄の伸びを直す）
- 変更ファイル: `css/v2.css`（`tools/edit_css_datefix_4c2.py`）、`tests/ui_smoke_driver.js`（`tools/edit_uismoke_datefix_4c2.py`、`tools/fix_uismoke_pcexpect_4c2.py`）
- `index.html`・`js/` は触っていません。`main` へのマージもしていません

### 8-1. 追加した CSS 規則の全文

`css/v2.css` の `@media (max-width: 640px)` の中、工事4c で足した規則の**直後**に追加しました。

```css
  /* 工事4c-2: 入力欄の高さを明示して揃える。
     iOS Safari は input[type="date"] を独自の内部部品で描くため、
     文字サイズ + padding から高さ・幅を素直に計算せず、日付欄だけ伸びていた。
     16px の文字 + 上下 padding 9px + 枠 1px を見込んで 40px に統一する
     （box-sizing: border-box が * で効いているので、これが外寸になる）。
     padding・border・角丸・色は変えない。 */
  input.form-input,
  select.form-input,
  input.member-row-input {
    height: 40px;
  }

  /* textarea は複数行なので高さを固定しない（現在このアプリには無い。将来用の保険）*/
  textarea.form-input {
    min-height: 40px;
  }

  /* 日付欄だけ iOS の独自描画を抑える。
     appearance を切って、幅と行の高さを他の欄と同じ土俵に乗せる。 */
  input[type="date"].form-input {
    -webkit-appearance: none;
    appearance: none;
    display: block;
    width: 100%;
    min-width: 0;
    line-height: normal;
  }

  /* iOS で日付の値が中央寄せになる既知の癖への対処（左寄せに揃える）*/
  input[type="date"].form-input::-webkit-date-and-time-value {
    text-align: left;
  }
```

### 8-2. 各指定の狙い

| 指定 | 狙い |
|---|---|
| `height: 40px`（input / select / member-row-input） | 外寸を数値で固定してしまい、ブラウザごとの高さ計算の差を無効にする。`box-sizing: border-box` が `*` で効いているので、これがそのまま枠の外寸になる |
| `textarea` だけ `min-height` | 複数行なので高さを固定すると入力が隠れる。**現在このアプリに `textarea` は 1 つもありません**（`index.html`・`js/ui.js` を検索して確認済み）。将来足したときに巻き込まれないための保険です |
| `-webkit-appearance: none; appearance: none;` | iOS が `type="date"` に当てる独自の内部部品の見た目・寸法計算を切り、ふつうのテキスト欄と同じ土俵に乗せる |
| `display: block; width: 100%; min-width: 0;` | iOS の日付欄は既定で `inline-block` 相当かつ内容に応じた最小幅を持つため、他の欄より広がったり縮んだりする。明示して幅を揃える |
| `line-height: normal` | 文字の縦位置がずれて枠が伸びるのを防ぐ |
| `::-webkit-date-and-time-value { text-align: left }` | iOS で日付の値が中央寄せになる既知の癖への対処。他の欄（左寄せ）と見た目を合わせる |

`padding`（9px 12px）・`border`・`border-radius`・色・`viewport` は変更していません。`!important` も使っていません（スクリプト側で、追加する宣言に `!important` と `padding` / `border` / `color` / `background` が含まれていないことを機械的に確認しています）。詳細度は `input[type="date"].form-input` が **0,2,1** で、`index.html` の `.form-input`（0,1,0）と工事4c の `input.form-input`（0,1,1）の両方を上回ります。

### 8-3. 通し確認の結果

**156 項目すべて通過 / 失敗 0**（工事4c の 150 + 今回の 6）。

幅を変えるためにページを iframe に読み込み、支払いモーダルを開いた状態で `getBoundingClientRect()` を実測しています。

**修正前後の実測値**（ヘッドレス Chrome）:

| 幅 | 4c-2 適用前 | 4c-2 適用後 |
|---|---|---|
| 390px（スマホ相当） | 日付 **46** / メモ 41 / 金額 41 / 支払った人 43（**バラバラ**） | **4 欄すべて 40 × 302**（揃った） |
| 1024px（PC 相当） | 日付 43 / メモ 40 / 金額 40 / 支払った人 42 | **同じ（43 / 40 / 40 / 42）＝無変更** |

今回足した確認:
```
ok   スマホ幅: 4 つの入力欄が測れる
ok   スマホ幅: 日付欄の高さが他の欄と揃う（4 欄が同じ高さ）
ok   スマホ幅: 4 欄の幅が揃う
ok   スマホ幅: 高さが 40px になっている
ok   PC 幅: 高さを 40px に固定していない（PC は従来のまま）
ok   PC 幅: 日付欄は Chrome 既定のまま（スマホ用の高さ指定が漏れていない）
```

その他: `node tests/run_all.js` **6 ファイル全通過**（CSS のみの変更なので工事4c から変化なし）、`node --check js/*.js tests/*.js` **全件 OK**、`tools/check_wiring.py` **OK**。

#### 途中で見つけたテスト側の誤り（正直に）
最初、依頼文にあった「幅 1024px では日付欄・メモ欄の高さが等しい」をそのまま期待値にしたところ **失敗しました**（日付 43px / メモ 40px）。

調べると、**Chrome は PC 幅でも日付欄を数 px 高く描いており、これは工事4c-2 の前からそう**でした（上の表の「適用前 1024px」）。今回の規則は `@media (max-width: 640px)` の中だけなので PC には届きません。つまり**実装ではなく期待値の思い込みが誤り**でした。

確認したいことは「PC が前と同じままか」なので、「高さが 40px に固定されていないこと」＋「日付欄が Chrome 既定どおりメモ欄より高いままであること」を見る形に直しました（`tools/fix_uismoke_pcexpect_4c2.py`）。判定の切り分けのため、**HEAD の CSS を使ったページを別に作って適用前の寸法も実測**しています。

#### ヘッドレス Chrome で確認できる範囲（重要）
今回の不具合は **iOS Safari 固有の描画**によるもので、ヘッドレス Chrome では再現しません。
上の確認で言えるのは「**Chrome では 4 欄の寸法が揃っており、PC 幅を崩していない**」までです。
**iOS 実機で実際に揃って見えるかどうかの判定は、花井の検収（§8-4）が唯一の確認手段**です。

### 8-4. 花井の検収手順

プレビュー: `https://kinsen-kanri-git-v2-o-ka-s-projects.vercel.app/`
**「テスト」始まりのグループ**で試してください。

**iPhone の Safari**
1. プレビューを開いてログイン →「テスト」始まりのグループを開く
2. 「＋ 支払いを記録」を開き、**日付・メモ・金額・支払った人の 4 欄が同じ高さ・同じ幅で揃っている**こと（日付欄だけ伸びていないこと）
3. **日付欄をタップしてもズームしない**こと（工事4c の効果が残っていること）
4. **日付ピッカーが今までどおり開き、選んだ日付が欄に表示される**こと（`appearance: none` で操作が壊れていないこと。ここが今回いちばん確認していただきたい点です）
5. 日付の文字が**左寄せ**で表示されること（中央寄せになっていないこと）
6. 「＋ グループを作成」「設定」「コードで参加」の各入力欄も、高さが揃っていること
7. メンバー名の入力欄（設定の中）も高さが揃っていること

**PC**
8. PC のブラウザで各モーダルを開き、**見た目が今までと変わっていない**こと（PC 幅には手を入れていません）

**本番との比較**
9. `https://kinsen-kanri.vercel.app/` は `main` のままなので、**まだ日付欄が伸びている**のが正しい状態です

### 8-5. 要判断・申し送り

1. **`-webkit-appearance: none` による日付欄の見え方の変化**（実機で確認してください）。iOS ではこの指定でカレンダーのアイコンや内部の装飾が消える／薄くなることがあります。**ピッカー自体はタップで開きます**が、「日付欄だとひと目で分かりにくい」と感じる場合は、次のどちらかで戻せます:
   - `appearance: none` をやめて `height` だけで揃える（揃いは弱くなるが装飾は残る）
   - 欄の左にカレンダーの絵文字を置く等、別の方法で日付欄だと示す
   どちらが良いかは実機の見た目を見てご判断ください
2. **PC 幅では日付欄が他より 3px 高いまま**です（Chrome 既定。工事4c より前からそうで、今回は対象外）。PC も揃えるなら、`@media` の外に同種の指定が要ります。気になるようなら次の工事で
3. **高さ 40px は固定値**です（`css/v2.css` のスマホ用ブロック）。padding を変えずに高さだけ決めているので、将来 `padding` を変えるときは 40px も見直してください
4. **`Claude outputs/` は未追跡のまま触っていません**（依頼どおり。`.gitignore` での扱いは別途）
5. 今回も**根本対処ではありません**（`body { position: fixed }` は据え置き）。工事4c §7-4 の申し送りはそのまま有効です
"""


def main():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"

    def fix(s):
        return s.replace("\n", nl) if nl != "\n" else s

    if "## 8. 4c-2 修正" in src:
        print("すでに追記済みです。何もしません。")
        return 0

    tail = fix(TAIL)
    n = src.count(tail)
    if n != 1:
        print("中止しました（末尾の一致 %d 件、1 件であるべき）。ファイルは変更していません。" % n)
        return 1
    if not src.rstrip().endswith(tail.rstrip()):
        print("中止しました（想定した末尾ではありません）。ファイルは変更していません。")
        return 1

    out = src.rstrip() + fix(ADDITION)
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("追記しました: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
