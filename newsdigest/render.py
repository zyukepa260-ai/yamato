"""Digest を HTML / Markdown / プレーンテキストに変換する。

HTMLメールは対応状況の差が大きいため、外部CSSやflexboxを使わず
インラインスタイルとテーブルレイアウトで組み立てる。
"""

from __future__ import annotations

import html

from .models import Digest, DigestItem

# 分野ごとの色（見出しの左罫線に使用）
CATEGORY_COLORS = {
    "法学・司法": "#8b1a1a",
    "政治・行政": "#1f4e79",
    "経済・ビジネス": "#1d6b4f",
    "国際": "#5b3a86",
    "テクノロジー": "#0f6f8b",
    "科学・医療": "#8b5a00",
    "社会": "#555f6b",
    "文化・その他": "#7a5c3e",
    "総合": "#444444",
}
DEFAULT_COLOR = "#444444"


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _color(category: str) -> str:
    return CATEGORY_COLORS.get(category, DEFAULT_COLOR)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def _html_sources(item: DigestItem) -> str:
    if not item.articles:
        return ""
    links = []
    for article in item.articles:
        label = _esc(article.source)
        links.append(
            f'<a href="{_esc(article.url)}" '
            f'style="color:#1a56b8;text-decoration:none;">{label}</a>'
        )
    return (
        '<div style="margin-top:6px;font-size:12px;color:#6b7280;line-height:1.8;">'
        "出典: " + " ｜ ".join(links) + "</div>"
    )


def _html_legal_item(index: int, item: DigestItem) -> str:
    tags = ""
    if item.tags:
        chips = "".join(
            '<span style="display:inline-block;background:#f3e8e8;color:#8b1a1a;'
            'font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px;">'
            f"{_esc(tag)}</span>"
            for tag in item.tags[:5]
        )
        tags = f'<div style="margin-top:8px;">{chips}</div>'

    significance = ""
    if item.significance:
        significance = (
            '<div style="margin-top:10px;padding:10px 12px;background:#fbf7f7;'
            'border-left:3px solid #8b1a1a;font-size:14px;color:#3f3f46;line-height:1.7;">'
            f'<strong style="color:#8b1a1a;">実務上の意味 — </strong>'
            f"{_esc(item.significance)}</div>"
        )

    return f"""
    <div style="margin:0 0 22px 0;padding-bottom:20px;border-bottom:1px solid #ececec;">
      <div style="font-size:17px;font-weight:700;color:#111827;line-height:1.5;">
        <span style="color:#8b1a1a;">{index}.</span> {_esc(item.title)}
      </div>
      <div style="margin-top:8px;font-size:14px;color:#374151;line-height:1.85;">
        {_esc(item.summary)}
      </div>
      {significance}
      {tags}
      {_html_sources(item)}
    </div>"""


def _html_plain_item(item: DigestItem) -> str:
    return f"""
    <div style="margin:0 0 16px 0;">
      <div style="font-size:15px;font-weight:600;color:#111827;line-height:1.5;">
        {_esc(item.title)}
      </div>
      <div style="margin-top:5px;font-size:14px;color:#4b5563;line-height:1.8;">
        {_esc(item.summary)}
      </div>
      {_html_sources(item)}
    </div>"""


def render_html(digest: Digest) -> str:
    """配信用のHTMLを組み立てる。"""
    legal_html = "".join(
        _html_legal_item(i, item) for i, item in enumerate(digest.legal_items, start=1)
    ) or '<div style="color:#6b7280;font-size:14px;">本日該当する記事はありませんでした。</div>'

    sections_html = []
    for section in digest.sections:
        items = "".join(_html_plain_item(item) for item in section.items)
        sections_html.append(
            f"""
      <div style="margin-top:30px;">
        <div style="font-size:15px;font-weight:700;color:{_color(section.category)};
                    border-left:4px solid {_color(section.category)};padding-left:10px;
                    margin-bottom:14px;">
          {_esc(section.category)}
        </div>
        {items}
      </div>"""
        )

    watchlist_html = ""
    if digest.watchlist:
        items = "".join(
            f'<li style="margin-bottom:6px;line-height:1.7;">{_esc(w)}</li>'
            for w in digest.watchlist
        )
        watchlist_html = f"""
      <div style="margin-top:34px;padding:16px 18px;background:#f8fafc;border-radius:8px;">
        <div style="font-size:14px;font-weight:700;color:#334155;margin-bottom:10px;">
          今後の注目ポイント
        </div>
        <ul style="margin:0;padding-left:20px;font-size:14px;color:#475569;">{items}</ul>
      </div>"""

    engine_label = "Claude による自動要約" if digest.engine == "claude" else "簡易要約（LLM未使用）"
    failed_note = ""
    if digest.failed_sources:
        failed_note = (
            f'<br>取得できなかったフィード: {len(digest.failed_sources)}件'
        )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(digest.date_label)} ニュースダイジェスト</title>
</head>
<body style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f4f5f7;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" border="0"
       style="max-width:680px;width:100%;background:#ffffff;border-radius:10px;
              font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Noto Sans JP',
              'Yu Gothic',Meiryo,sans-serif;">
  <tr><td style="padding:28px 32px 20px 32px;border-bottom:3px solid #8b1a1a;">
    <div style="font-size:12px;color:#8b1a1a;letter-spacing:1.5px;font-weight:700;">
      MORNING NEWS DIGEST
    </div>
    <div style="font-size:24px;font-weight:700;color:#111827;margin-top:6px;">
      {_esc(digest.date_label)}
    </div>
    <div style="font-size:14px;color:#4b5563;margin-top:10px;line-height:1.7;">
      {_esc(digest.headline)}
    </div>
  </td></tr>

  <tr><td style="padding:26px 32px 0 32px;">
    <div style="font-size:16px;font-weight:700;color:#8b1a1a;padding-bottom:10px;
                border-bottom:2px solid #8b1a1a;margin-bottom:20px;">
      法学・司法［重点］
    </div>
    {legal_html}
  </td></tr>

  <tr><td style="padding:6px 32px 0 32px;">
    {"".join(sections_html)}
    {watchlist_html}
  </td></tr>

  <tr><td style="padding:24px 32px 28px 32px;">
    <div style="border-top:1px solid #e5e7eb;padding-top:14px;font-size:11px;
                color:#9ca3af;line-height:1.8;">
      収集 {digest.total_collected}件 → 重複除去後 {digest.total_after_dedupe}件 ／ {engine_label}{failed_note}
      <br>要約は自動生成です。重要な判断の前には必ず原典（出典リンク先）をご確認ください。
    </div>
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Markdown / プレーンテキスト
# ---------------------------------------------------------------------------
def render_markdown(digest: Digest) -> str:
    lines: list[str] = [
        f"# {digest.date_label} ニュースダイジェスト",
        "",
        digest.headline,
        "",
        "## 法学・司法［重点］",
        "",
    ]

    if not digest.legal_items:
        lines.append("本日該当する記事はありませんでした。")
        lines.append("")

    for index, item in enumerate(digest.legal_items, start=1):
        lines.append(f"### {index}. {item.title}")
        lines.append("")
        lines.append(item.summary)
        if item.significance:
            lines.append("")
            lines.append(f"> **実務上の意味** — {item.significance}")
        if item.tags:
            lines.append("")
            lines.append("`" + "` `".join(item.tags[:5]) + "`")
        if item.articles:
            links = " ｜ ".join(f"[{a.source}]({a.url})" for a in item.articles)
            lines.append("")
            lines.append(f"出典: {links}")
        lines.append("")

    for section in digest.sections:
        lines.append(f"## {section.category}")
        lines.append("")
        for item in section.items:
            lines.append(f"**{item.title}**")
            lines.append("")
            if item.summary:
                lines.append(item.summary)
                lines.append("")
            if item.articles:
                links = " ｜ ".join(f"[{a.source}]({a.url})" for a in item.articles)
                lines.append(f"出典: {links}")
                lines.append("")

    if digest.watchlist:
        lines.append("## 今後の注目ポイント")
        lines.append("")
        lines.extend(f"- {w}" for w in digest.watchlist)
        lines.append("")

    engine_label = "Claude による自動要約" if digest.engine == "claude" else "簡易要約（LLM未使用）"
    lines.append("---")
    lines.append(
        f"収集 {digest.total_collected}件 → 重複除去後 {digest.total_after_dedupe}件 ／ {engine_label}"
    )
    return "\n".join(lines)


def render_text(digest: Digest) -> str:
    """HTMLメールを表示できない環境向けのプレーンテキスト版。"""
    lines: list[str] = [
        f"{digest.date_label} ニュースダイジェスト",
        "=" * 40,
        "",
        digest.headline,
        "",
        "■ 法学・司法［重点］",
        "",
    ]
    for index, item in enumerate(digest.legal_items, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"   {item.summary}")
        if item.significance:
            lines.append(f"   [実務上の意味] {item.significance}")
        for article in item.articles:
            lines.append(f"   - {article.source}: {article.url}")
        lines.append("")

    for section in digest.sections:
        lines.append(f"■ {section.category}")
        lines.append("")
        for item in section.items:
            lines.append(f"・{item.title}")
            if item.summary:
                lines.append(f"   {item.summary}")
            for article in item.articles:
                lines.append(f"   - {article.source}: {article.url}")
            lines.append("")

    if digest.watchlist:
        lines.append("■ 今後の注目ポイント")
        lines.extend(f"・{w}" for w in digest.watchlist)
        lines.append("")

    return "\n".join(lines)


def render_slack(digest: Digest, max_legal: int = 6, max_other: int = 8) -> str:
    """Slack / Discord 向けの短縮版（mrkdwn）。"""
    lines = [f"*{digest.date_label} ニュースダイジェスト*", "", digest.headline, "", "*⚖️ 法学・司法［重点］*"]
    for index, item in enumerate(digest.legal_items[:max_legal], start=1):
        link = item.articles[0].url if item.articles else ""
        title = f"<{link}|{item.title}>" if link else item.title
        lines.append(f"{index}. {title}")
        lines.append(f"　{item.summary}")
        if item.significance:
            lines.append(f"　_実務上の意味: {item.significance}_")
    lines.append("")

    shown = 0
    for section in digest.sections:
        if shown >= max_other:
            break
        lines.append(f"*{section.category}*")
        for item in section.items:
            if shown >= max_other:
                break
            link = item.articles[0].url if item.articles else ""
            title = f"<{link}|{item.title}>" if link else item.title
            lines.append(f"・{title}")
            shown += 1
    return "\n".join(lines)
