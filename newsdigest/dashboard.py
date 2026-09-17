"""ダッシュボード形式のHTMLを生成する。

メール版(render.py)との違い:
- メールはHTMLメールの制約上、静的・インラインCSSのみ
- ダッシュボードは絞り込み検索・分野フィルタ・グラフを備えた単一HTMLファイル

外部CDNに依存しない自己完結型のため、ファイルを直接開くだけで動作し、
オフラインでも表示できる。
"""

from __future__ import annotations

import html
import json
from string import Template

from .models import Digest
from .ranker import LEGAL_CATEGORY

# ---------------------------------------------------------------------------
# 配色（dataviz の検証済みパレットより）
#   グラフは「強調(emphasis)」形式: 重点分野である法学だけをアクセント色にし、
#   他分野は非強調グレーにする。アクセント×グレーの識別性は検証スクリプトで
#   確認済み（CVD ΔE 15.9 / 通常視 17.8 / コントラスト 3:1 以上、明暗両モード）。
# ---------------------------------------------------------------------------
ACCENT_LIGHT = "#2a78d6"
ACCENT_DARK = "#3987e5"
DEEMPHASIS = "#898781"


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _payload(digest: Digest) -> dict:
    """JSに渡すデータ。描画と絞り込みはブラウザ側で行う。"""
    groups = []

    if digest.legal_items:
        groups.append(
            {
                "category": LEGAL_CATEGORY,
                "emphasis": True,
                "items": [
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "significance": item.significance,
                        "tags": item.tags[:5],
                        "sources": [
                            {"label": a.source, "url": a.url} for a in item.articles
                        ],
                    }
                    for item in digest.legal_items
                ],
            }
        )

    for section in digest.sections:
        groups.append(
            {
                "category": section.category,
                "emphasis": False,
                "items": [
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "significance": "",
                        "tags": [],
                        "sources": [
                            {"label": a.source, "url": a.url} for a in item.articles
                        ],
                    }
                    for item in section.items
                ],
            }
        )

    return {
        "dateLabel": digest.date_label,
        "headline": digest.headline,
        "engine": digest.engine,
        "generatedAt": digest.generated_at.strftime("%Y-%m-%d %H:%M"),
        "groups": groups,
        "watchlist": digest.watchlist,
        "stats": {
            "collected": digest.total_collected,
            "afterDedupe": digest.total_after_dedupe,
            "legalCount": len(digest.legal_items),
            "sectionCount": len(digest.sections),
            "totalSources": digest.total_sources,
            "failedSources": digest.failed_sources,
        },
        "legalCategory": LEGAL_CATEGORY,
    }


_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>
:root {
  color-scheme: light;
  --page:           #f9f9f7;
  --surface:        #fcfcfb;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --accent:         #2a78d6;
  --accent-wash:    rgba(42,120,214,0.09);
  --deemphasis:     #898781;
  --good:           #0ca30c;
  --critical:       #d03b3b;
  --shadow:         0 1px 2px rgba(11,11,11,0.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:           #0d0d0d;
    --surface:        #1a1a19;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --accent:         #3987e5;
    --accent-wash:    rgba(57,135,229,0.15);
    --deemphasis:     #898781;
    --good:           #0ca30c;
    --critical:       #d03b3b;
    --shadow:         none;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page:           #0d0d0d;
  --surface:        #1a1a19;
  --text-primary:   #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted:     #898781;
  --gridline:       #2c2c2a;
  --baseline:       #383835;
  --border:         rgba(255,255,255,0.10);
  --accent:         #3987e5;
  --accent-wash:    rgba(57,135,229,0.15);
  --deemphasis:     #898781;
  --good:           #0ca30c;
  --critical:       #d03b3b;
  --shadow:         none;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", "Yu Gothic", Meiryo, sans-serif;
  font-size: 15px;
  line-height: 1.75;
}
.wrap { max-width: 1120px; margin: 0 auto; padding: 28px 16px 64px; }

/* ---------- ヘッダー ---------- */
header { margin-bottom: 26px; }
.eyebrow {
  font-size: 11px; font-weight: 700; letter-spacing: 1.6px;
  color: var(--accent); text-transform: uppercase;
}
h1 { font-size: 27px; font-weight: 700; margin: 6px 0 0; letter-spacing: -0.01em; }
.headline {
  margin-top: 12px; color: var(--text-secondary); font-size: 15px;
  max-width: 76ch;
}
.meta-row {
  margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; padding: 3px 10px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--text-secondary);
  background: var(--surface);
}
.badge b { color: var(--text-primary); font-weight: 600; }
.theme-toggle {
  margin-left: auto; font: inherit; font-size: 12px; cursor: pointer;
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 8px; padding: 5px 12px;
}
.theme-toggle:hover { color: var(--text-primary); }

/* ---------- KPI ---------- */
.kpi-grid {
  display: grid; gap: 12px; margin-bottom: 14px;
  grid-template-columns: 1.5fr 1fr 1fr 1fr 1fr;
}
.tile {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; box-shadow: var(--shadow);
}
.tile .label {
  font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;
}
.tile .value { font-size: 26px; font-weight: 600; line-height: 1.25; }
.tile .sub { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
.tile.hero { border-color: var(--accent); background: var(--accent-wash); }
.tile.hero .value { font-size: 50px; color: var(--accent); letter-spacing: -0.02em; }
.tile.hero .label { color: var(--text-primary); font-weight: 600; }

/* ---------- グラフ ---------- */
.panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px; margin-bottom: 14px;
  box-shadow: var(--shadow);
}
.panel-head {
  display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px;
}
.panel-title { font-size: 14px; font-weight: 700; }
.panel-note { font-size: 11.5px; color: var(--text-muted); }
.panel-head .linkish { margin-left: auto; }
.linkish {
  font: inherit; font-size: 11.5px; background: none; border: none; cursor: pointer;
  color: var(--text-secondary); text-decoration: underline; padding: 0;
}
.linkish:hover { color: var(--text-primary); }

.bar-row {
  display: grid; grid-template-columns: 116px 1fr;
  align-items: center; gap: 10px;
  padding: 2px 0;              /* 隣接バー間の 2px サーフェスギャップ */
  cursor: default;
}
.bar-label {
  font-size: 12px; color: var(--text-secondary);
  text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bar-track {
  height: 18px; display: flex; align-items: center;
  border-left: 1px solid var(--baseline);   /* 基線はバーの起点に揃える */
  padding-left: 1px;
}
.bar {
  height: 18px;                /* 24px 以下 */
  border-radius: 0 4px 4px 0;  /* データ側の端だけ丸め、基線側は角のまま */
  background: var(--deemphasis);
  min-width: 2px;
  transition: filter .12s;
}
.bar-row.is-accent .bar { background: var(--accent); }
.bar-row:hover .bar { filter: brightness(1.12); }
.bar-value {                  /* 値はバーの先端に直接ラベルする */
  font-size: 12px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  margin-left: 8px; white-space: nowrap;
}

table.data { border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }
table.data th, table.data td {
  text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--gridline);
}
table.data td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.data th { color: var(--text-secondary); font-weight: 600; }

/* ---------- 絞り込み ---------- */
.controls {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin: 22px 0 6px;
}
#q {
  font: inherit; font-size: 13px; padding: 8px 12px; min-width: 260px; flex: 0 1 320px;
  border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text-primary);
}
#q:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
.chip {
  font: inherit; font-size: 12px; padding: 5px 12px; cursor: pointer;
  border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text-secondary);
}
.chip:hover { color: var(--text-primary); }
.chip[aria-pressed="true"] {
  background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600;
}
.count { font-size: 12px; color: var(--text-muted); margin-left: auto; }

/* ---------- 記事 ---------- */
.group { margin-top: 26px; }
.group-head {
  display: flex; align-items: center; gap: 9px;
  padding-bottom: 8px; margin-bottom: 14px;
  border-bottom: 1px solid var(--gridline);
}
.group-dot { width: 9px; height: 9px; border-radius: 2px; background: var(--deemphasis); }
.group.is-accent .group-dot { background: var(--accent); }
.group-name { font-size: 15px; font-weight: 700; }
.group.is-accent .group-name { color: var(--accent); }
.group-tag {
  font-size: 10.5px; font-weight: 700; letter-spacing: .06em;
  border: 1px solid var(--accent); color: var(--accent);
  padding: 1px 7px; border-radius: 4px;
}
.group-count { margin-left: auto; font-size: 11.5px; color: var(--text-muted); }

.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; margin-bottom: 10px;
  box-shadow: var(--shadow);
}
.card h3 { margin: 0; font-size: 16px; font-weight: 700; line-height: 1.55; }
.group.is-accent .card h3 { font-size: 17px; }
.card .body { margin-top: 7px; color: var(--text-secondary); font-size: 14.5px; }
.sig {
  margin-top: 11px; padding: 10px 13px; border-radius: 7px;
  background: var(--accent-wash); border-left: 3px solid var(--accent);
  font-size: 14px; color: var(--text-secondary);
}
.sig b { color: var(--accent); }
.tags { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
  font-size: 11px; padding: 2px 9px; border-radius: 999px;
  background: var(--accent-wash); color: var(--accent);
}
.srcs { margin-top: 10px; font-size: 12px; color: var(--text-muted); }
.srcs a { color: var(--accent); text-decoration: none; }
.srcs a:hover { text-decoration: underline; }
.srcs .sep { color: var(--border); margin: 0 3px; }

.empty {
  padding: 34px; text-align: center; color: var(--text-muted); font-size: 14px;
  background: var(--surface); border: 1px dashed var(--border); border-radius: 10px;
}

/* ---------- 注目ポイント / 情報源 ---------- */
ul.watch { margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 14px; }
ul.watch li { margin-bottom: 5px; }
details.sources { margin-top: 14px; }
details.sources summary {
  cursor: pointer; font-size: 12.5px; color: var(--text-secondary);
}
.status { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; }
.status-icon { font-weight: 700; }
.status.ok .status-icon { color: var(--good); }
.status.bad .status-icon { color: var(--critical); }
.fail-list {
  margin: 10px 0 0; padding-left: 18px; font-size: 12px;
  color: var(--text-muted); max-height: 260px; overflow-y: auto;
}
footer {
  margin-top: 34px; padding-top: 16px; border-top: 1px solid var(--gridline);
  font-size: 11.5px; color: var(--text-muted);
}
.hidden { display: none !important; }

@media (max-width: 860px) {
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .tile.hero { grid-column: 1 / -1; }
  .bar-row { grid-template-columns: 92px 1fr; }
  .count { width: 100%; margin-left: 0; }
}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="eyebrow">Morning News Digest</div>
  <h1>${date_label}</h1>
  <p class="headline">${headline}</p>
  <div class="meta-row">
    <span class="badge">要約: <b>${engine_label}</b></span>
    <span class="badge">生成: <b>${generated_at}</b></span>
    <span class="badge status ${source_status_class}">
      <span class="status-icon">${source_status_icon}</span>情報源 <b>${alive_sources}/${total_sources}</b>
    </span>
    <button class="theme-toggle" id="themeToggle" type="button">表示切替</button>
  </div>
</header>

<div class="kpi-grid">
  <div class="tile hero">
    <div class="label">法学・司法トピック</div>
    <div class="value">${legal_count}</div>
    <div class="sub">重点分野として最優先で収集</div>
  </div>
  <div class="tile">
    <div class="label">収集記事</div>
    <div class="value">${collected}</div>
    <div class="sub">全フィード合計</div>
  </div>
  <div class="tile">
    <div class="label">重複除去後</div>
    <div class="value">${after_dedupe}</div>
    <div class="sub">${dedupe_note}</div>
  </div>
  <div class="tile">
    <div class="label">掲載分野</div>
    <div class="value">${section_count}</div>
    <div class="sub">法学以外の分野数</div>
  </div>
  <div class="tile">
    <div class="label">注目ポイント</div>
    <div class="value">${watch_count}</div>
    <div class="sub">続報を追う論点</div>
  </div>
</div>

<div class="panel">
  <div class="panel-head">
    <span class="panel-title">分野別のトピック数</span>
    <span class="panel-note">青が重点分野（法学・司法）</span>
    <button class="linkish" id="tableToggle" type="button">表で見る</button>
  </div>
  <div id="chart"></div>
  <div id="chartTable" class="hidden"></div>
</div>

<div class="controls">
  <input id="q" type="search" placeholder="キーワードで絞り込み（例: 労働、個人情報）" autocomplete="off">
  <div id="chips"></div>
  <span class="count" id="count"></span>
</div>

<div id="groups"></div>
<div id="noResult" class="empty hidden">該当するトピックがありません。</div>

${watchlist_html}
${sources_html}

<footer>
  収集 ${collected}件 → 重複除去後 ${after_dedupe}件 ／ ${engine_label}<br>
  要約は自動生成です。法的な判断の前には必ず出典リンク先の原典をご確認ください。
</footer>

</div>

<script id="data" type="application/json">${data_json}</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var LEGAL = DATA.legalCategory;
  var activeCategory = "ALL";
  var query = "";

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  /* ---------- グラフ（強調形式の横棒） ---------- */
  function drawChart() {
    var rows = DATA.groups.map(function (g) {
      return { name: g.category, value: g.items.length, accent: g.emphasis };
    }).sort(function (a, b) { return b.value - a.value; });

    var max = rows.reduce(function (m, r) { return Math.max(m, r.value); }, 0) || 1;
    var chart = document.getElementById("chart");
    chart.textContent = "";

    rows.forEach(function (r) {
      var row = el("div", "bar-row" + (r.accent ? " is-accent" : ""));
      row.appendChild(el("div", "bar-label", r.name));
      var track = el("div", "bar-track");
      var bar = el("div", "bar");
      bar.style.width = "calc(" + Math.max((r.value / max) * 92, 1) + "% )";
      /* ホバー時の説明（ツールチップ層） */
      row.title = r.name + ": " + r.value + "件"
        + (r.accent ? "（重点分野）" : "");
      track.appendChild(bar);
      track.appendChild(el("div", "bar-value", String(r.value)));  /* 先端に直接ラベル */
      row.appendChild(track);
      chart.appendChild(row);
    });

    /* 同じ数値を表でも読めるようにする（色に依存しない経路） */
    var table = el("table", "data");
    var head = el("tr");
    head.appendChild(el("th", null, "分野"));
    var th = el("th", null, "トピック数"); th.style.textAlign = "right";
    head.appendChild(th);
    table.appendChild(head);
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("td", null, r.name + (r.accent ? "（重点）" : "")));
      tr.appendChild(el("td", "num", String(r.value)));
      table.appendChild(tr);
    });
    var wrapper = document.getElementById("chartTable");
    wrapper.textContent = "";
    wrapper.appendChild(table);
  }

  document.getElementById("tableToggle").addEventListener("click", function () {
    var t = document.getElementById("chartTable");
    var c = document.getElementById("chart");
    var showTable = t.classList.contains("hidden");
    t.classList.toggle("hidden", !showTable);
    c.classList.toggle("hidden", showTable);
    this.textContent = showTable ? "グラフで見る" : "表で見る";
  });

  /* ---------- 分野チップ ---------- */
  function drawChips() {
    var box = document.getElementById("chips");
    var cats = ["ALL"].concat(DATA.groups.map(function (g) { return g.category; }));
    cats.forEach(function (cat) {
      var b = el("button", "chip", cat === "ALL" ? "すべて" : cat);
      b.type = "button";
      b.setAttribute("aria-pressed", String(cat === activeCategory));
      b.addEventListener("click", function () {
        activeCategory = cat;
        Array.prototype.forEach.call(box.children, function (c) {
          c.setAttribute("aria-pressed", String(c === b));
        });
        render();
      });
      box.appendChild(b);
    });
  }

  /* ---------- 一覧 ---------- */
  function matches(item) {
    if (!query) return true;
    var hay = (item.title + " " + item.summary + " " + item.significance
      + " " + item.tags.join(" ")).toLowerCase();
    return hay.indexOf(query) !== -1;
  }

  function buildCard(item, accent) {
    var card = el("div", "card");
    card.appendChild(el("h3", null, item.title));
    if (item.summary) card.appendChild(el("div", "body", item.summary));

    if (accent && item.significance) {
      var sig = el("div", "sig");
      var b = el("b", null, "実務上の意味 — ");
      sig.appendChild(b);
      sig.appendChild(document.createTextNode(item.significance));
      card.appendChild(sig);
    }
    if (item.tags && item.tags.length) {
      var tags = el("div", "tags");
      item.tags.forEach(function (t) { tags.appendChild(el("span", "tag", t)); });
      card.appendChild(tags);
    }
    if (item.sources && item.sources.length) {
      var srcs = el("div", "srcs");
      srcs.appendChild(document.createTextNode("出典: "));
      item.sources.forEach(function (s, i) {
        if (i) {
          var sep = el("span", "sep", "｜");
          srcs.appendChild(sep);
        }
        var a = el("a", null, s.label);
        a.href = s.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        srcs.appendChild(a);
      });
      card.appendChild(srcs);
    }
    return card;
  }

  function render() {
    var host = document.getElementById("groups");
    host.textContent = "";
    var shown = 0;

    DATA.groups.forEach(function (g) {
      if (activeCategory !== "ALL" && g.category !== activeCategory) return;
      var items = g.items.filter(matches);
      if (!items.length) return;
      shown += items.length;

      var wrap = el("div", "group" + (g.emphasis ? " is-accent" : ""));
      var head = el("div", "group-head");
      head.appendChild(el("span", "group-dot"));
      head.appendChild(el("span", "group-name", g.category));
      if (g.emphasis) head.appendChild(el("span", "group-tag", "重点"));
      head.appendChild(el("span", "group-count", items.length + "件"));
      wrap.appendChild(head);
      items.forEach(function (it) { wrap.appendChild(buildCard(it, g.emphasis)); });
      host.appendChild(wrap);
    });

    document.getElementById("noResult").classList.toggle("hidden", shown > 0);
    var total = DATA.groups.reduce(function (n, g) { return n + g.items.length; }, 0);
    document.getElementById("count").textContent =
      (shown === total) ? ("全 " + total + " トピック") : ("表示中 " + shown + " / " + total + " トピック");
  }

  document.getElementById("q").addEventListener("input", function () {
    query = this.value.trim().toLowerCase();
    render();
  });

  /* ---------- 表示モード切替 ---------- */
  document.getElementById("themeToggle").addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.getAttribute("data-theme") === "dark";
    if (!root.getAttribute("data-theme")) {
      dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    root.setAttribute("data-theme", dark ? "light" : "dark");
  });

  drawChart();
  drawChips();
  render();
})();
</script>
</body>
</html>
""")


def render_dashboard(digest: Digest) -> str:
    """ダッシュボード形式のHTML（単一ファイル・外部依存なし）を返す。"""
    data = _payload(digest)
    stats = data["stats"]

    failed = stats["failedSources"]
    total_sources = stats.get("totalSources") or 0
    if not total_sources:
        # デモ等で総数が未設定の場合は、分かっている情報だけで辻褄を合わせる
        total_sources = len(failed) + (1 if stats["collected"] else 0)
    alive = max(total_sources - len(failed), 0)

    dedupe_note = "重複をまとめた後の件数"
    if stats["collected"]:
        removed = stats["collected"] - stats["afterDedupe"]
        if removed > 0:
            dedupe_note = f"{removed}件の重複を統合"

    watchlist_html = ""
    if data["watchlist"]:
        items = "".join(f"<li>{_esc(w)}</li>" for w in data["watchlist"])
        watchlist_html = (
            '<div class="panel" style="margin-top:26px;">'
            '<div class="panel-head"><span class="panel-title">今後の注目ポイント</span></div>'
            f'<ul class="watch">{items}</ul></div>'
        )

    sources_html = ""
    if failed:
        items = "".join(f"<li>{_esc(name)}</li>" for name in failed)
        sources_html = (
            '<details class="sources"><summary>'
            f"取得できなかった情報源 {len(failed)}件を表示"
            f'</summary><ul class="fail-list">{items}</ul></details>'
        )

    engine_label = "Claude による自動要約" if data["engine"] == "claude" else "簡易要約（LLM未使用）"
    status_ok = not failed
    # 状態は色だけに頼らず、記号＋ラベルで示す
    return _TEMPLATE.substitute(
        title=f"{data['dateLabel']} ニュースダイジェスト",
        date_label=_esc(data["dateLabel"]),
        headline=_esc(data["headline"]),
        engine_label=_esc(engine_label),
        generated_at=_esc(data["generatedAt"]),
        source_status_class="ok" if status_ok else "bad",
        source_status_icon="●" if status_ok else "▲",
        alive_sources=alive,
        total_sources=total_sources,
        legal_count=stats["legalCount"],
        collected=stats["collected"],
        after_dedupe=stats["afterDedupe"],
        dedupe_note=_esc(dedupe_note),
        section_count=stats["sectionCount"],
        watch_count=len(data["watchlist"]),
        watchlist_html=watchlist_html,
        sources_html=sources_html,
        # </script> による早期終了を防ぐ
        data_json=json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
    )
