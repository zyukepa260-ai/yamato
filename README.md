# 毎朝8時のニュースダイジェスト（法学重点）

毎日あらゆる分野のニュースを自動収集し、**法学・法律関連を最重点**でまとめて、
**毎朝8時（日本時間）にメールで届ける**システムです。

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐
│ 43フィード │ → │ 重複除去  │ → │ 法学重み  │ → │ Claude   │ → │ 毎朝8時 │
│ を並列収集 │   │          │   │ でランク  │   │ が要約   │   │ に配信  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └────────┘
```

## 特徴

- **法学分野を構造的に優先** — 情報源の約半分（24系統）が法律・司法系。
  さらに「最高裁」「違憲」「法改正」などの法律用語に重み付けしたスコアリングを行い、
  一般ニュースが大量に流れた日でも法学トピックが最低8件は確保されます。
- **各法学トピックに「実務上の意味」** — 何が起きたかだけでなく、
  誰にどう影響するのかまで要約します。
- **リンクの捏造が起こらない設計** — 記事URLはモデルに生成させず、
  こちらが渡した記事番号で参照させ、プログラム側でURLに復元します。
- **止まりにくい** — フィードが1つ落ちても、APIキーが無くても、Claudeが失敗しても、
  簡易要約に自動で切り替えて配信を継続します。
- **依存が3つだけ** — feedparser / PyYAML / anthropic。

---

## 1. セットアップ

```bash
git clone <このリポジトリ>
cd yamato

python3 -m venv .venv && source .venv/bin/activate   # 任意
pip install -r requirements.txt

cp .env.example .env
```

`.env` を開いて、最低限この2つを設定します。

### (a) 要約用の Claude APIキー

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

> APIキーが無くても動きます。その場合は「収集した記事の見出しと配信元の要約を
> 分野別に並べただけ」の簡易版になります（新しい文章は生成されません）。

キーは <https://console.anthropic.com/> で取得できます。

### (b) メールの送信設定（Gmail の例）

```bash
DIGEST_NOTIFIERS=email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=あなた@gmail.com
SMTP_PASSWORD=アプリパスワード16桁
MAIL_FROM=あなた@gmail.com
MAIL_TO=あなた@gmail.com
```

> **重要**: Gmail では通常のログインパスワードは使えません。
> [アプリパスワード](https://myaccount.google.com/apppasswords) を発行して使ってください
> （2段階認証の有効化が必要です）。

Slack や Discord に送りたい場合は `DIGEST_NOTIFIERS=email,slack` のように並べ、
`SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL` を設定してください。
`file` を指定すると `archive/` にHTMLとMarkdownを書き出すだけになります（動作確認に便利）。

---

## 2. 動作確認

設定したら、**この順番で**確認するのが確実です。

```bash
# ① 配信経路の確認（ネットワーク不要・サンプル内容が届く）
python -m newsdigest demo

# ② 情報源の疎通確認（どのフィードが生きているか一覧表示）
python -m newsdigest doctor

# ③ 実際に収集して中身だけ確認（配信しない）
python -m newsdigest preview

# ④ 本番と同じ動作（収集して配信）
python -m newsdigest run
```

### `doctor` について（重要）

同梱の `config/sources.yaml` に並べたURLは、**開発環境から外部接続ができなかったため
生死を検証できていません**。初回は必ず `doctor` を実行して、
応答しないフィードを `enabled: false` にするかURLを修正してください。

```
  [OK] 裁判所 新着判例                  18件  0.8s
  [NG] 法務省 新着情報                  HTTP 404
  ...
  生存: 38/43  （うち法学分野: 21件）
```

応答しないフィードがあってもパイプラインは自動でスキップするため、
配信自体は止まりません。ただし**法学分野が全滅すると重点セクションが空になる**ため、
`doctor` はその場合に警告とエラー終了を返します。

---

## 3. 毎朝8時に自動実行する

### 方法A: GitHub Actions（推奨・PCを起動しておく必要なし）

`.github/workflows/daily-digest.yml` が同梱済みです。

1. このリポジトリをGitHubにpush
2. **Settings → Secrets and variables → Actions** で以下を登録

   | Secret 名 | 内容 |
   |---|---|
   | `ANTHROPIC_API_KEY` | Claude APIキー |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | 送信元アドレス |
   | `SMTP_PASSWORD` | アプリパスワード |
   | `MAIL_FROM` | 送信元アドレス |
   | `MAIL_TO` | 宛先（カンマ区切りで複数可） |

3. **Actions** タブから一度手動実行（`Run workflow`）して動作を確認

スケジュールは `cron: "0 23 * * *"`（23:00 UTC = **翌日08:00 JST**）です。

> GitHub Actions のスケジュール実行は、混雑時に数分〜十数分遅れることがあります。
> 分単位の正確さが必要な場合は方法Bを使ってください。

### 方法B: 自分のPC / サーバー

**cron を使う場合**（8:00に実行）:

```cron
0 8 * * * cd /path/to/yamato && /path/to/.venv/bin/python -m newsdigest run >> /var/log/digest.log 2>&1
```

**常駐スクリプトを使う場合**:

```bash
python scripts/run_local_scheduler.py            # 毎日8:00
python scripts/run_local_scheduler.py --at 07:30 # 時刻変更
python scripts/run_local_scheduler.py --once     # 今すぐ1回
```

---

## 4. カスタマイズ

### 情報源を追加・削除する — `config/sources.yaml`

キーワードを足すだけで守備範囲が広がります（Googleニュース検索を利用）:

```yaml
google_news:
  queries:
    - { q: "行政事件訴訟 OR 国家賠償", name: "行政訴訟", category: "法学・司法", weight: 2.0 }
```

特定サイトのRSSを直接追加する場合:

```yaml
feeds:
  - name: "○○法律事務所ブログ"
    url: "https://example.com/feed"
    category: "法学・司法"
    weight: 2.0
```

`weight` は重要度の係数です。一次情報（裁判所・官公庁）には 2.0〜2.6、
一般ニュースには 1.0 程度を目安にしてください。

### 法学キーワードの重み — `newsdigest/ranker.py`

`LEGAL_TERMS_JA` / `LEGAL_TERMS_EN` の辞書を編集します。
関心のある分野（例: 医事法、租税法）の用語を追加すると、その分野が優先されます。

```python
LEGAL_TERMS_JA = {
    "最高裁": 3.0,
    "医療過誤": 2.5,   # ← 追加
}
```

### 分量の調整 — `.env`

| 変数 | 既定 | 説明 |
|---|---|---|
| `DIGEST_LOOKBACK_HOURS` | 24 | 何時間前までの記事を対象にするか |
| `DIGEST_MAX_ARTICLES` | 140 | Claudeに渡す記事数の上限（コストに直結） |
| `DIGEST_LEGAL_MIN` | 8 | 法学セクションの最低件数 |
| `DIGEST_MODEL` | `claude-opus-5` | 要約に使うモデル |

---

## 5. 運用コストの目安

記事140件を渡した場合、1日あたり入力約25,000トークン・出力数千トークンです。
`claude-opus-5`（入力 $5 / 出力 $25 per 1M tokens）で **1日あたり約$0.2〜0.3、月$6〜10程度**
が目安になります。

抑えたい場合は次のいずれかを:

- `DIGEST_MAX_ARTICLES` を 60〜80 に下げる
- `.env` で `DIGEST_MODEL=claude-sonnet-5` に変更する（入力$2 / 出力$10）

---

## 6. 仕組み

| モジュール | 役割 |
|---|---|
| `sources.py` | `sources.yaml` から取得対象フィードを組み立てる（Googleニュース検索URLも生成） |
| `collector.py` | 43フィードを並列取得。1つが落ちても全体を止めない |
| `dedupe.py` | URL正規化＋見出しの文字バイグラム類似度で重複を圧縮 |
| `ranker.py` | 法律用語の重み付けでスコアリングし、法学枠を確保して選抜 |
| `summarizer.py` | Claudeに構造化出力(JSON schema)で要約させる。失敗時は簡易要約 |
| `render.py` | HTMLメール / Markdown / テキスト / Slack形式に変換 |
| `notifiers/` | メール(SMTP)・Slack・Discord・ファイル出力 |
| `pipeline.py` | 上記を順に実行し、結果を `archive/` に保存 |

重複判定は Jaccard係数と重なり率の両方を満たす場合のみ重複とみなします。
これにより「最高裁が判断」と「最高裁が判断を示す」は統合しつつ、
「東京地裁、賠償命令」と「大阪地裁、賠償命令」は別ニュースとして残します。

---

## 7. 注意点

- **要約は自動生成です。** 法的な判断を行う前には、必ず出典リンク先の原典
  （判決文・官報・条文）をご確認ください。メール末尾にも同趣旨の注記が入ります。
- **同梱フィードURLは未検証です。** 上記のとおり `doctor` で確認してください。
- Googleニュース検索は検索結果の提供であり、各記事の著作権は各媒体に帰属します。
  本システムは見出しと配信元提供の要約、およびリンクのみを扱います。
- `archive/` の生成物は `.gitignore` 済みです（リポジトリを汚しません）。

---

## 8. テスト

```bash
pip install pytest
python -m pytest tests/ -q
```

重複判定・法学スコアリング・HTMLエスケープ・Claude呼び出し（モック）・
パイプライン通し実行を含む52件のテストが入っています。
