from datetime import datetime, timezone

from newsdigest.models import Article, Digest, DigestItem, DigestSection
from newsdigest.render import render_html, render_markdown, render_slack, render_text

NOW = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


def build_digest() -> Digest:
    article = Article(
        title="記事タイトル", url="https://example.com/a", source="出典A",
        category="法学・司法",
    )
    digest = Digest(generated_at=NOW, engine="claude", headline="今日の概況")
    digest.legal_items = [
        DigestItem(
            title="法学トピック", summary="要約本文", significance="実務上の意味",
            tags=["個人情報"], articles=[article],
        )
    ]
    digest.sections = [
        DigestSection(category="経済・ビジネス",
                      items=[DigestItem(title="経済トピック", summary="要約", articles=[article])])
    ]
    digest.watchlist = ["注目点1"]
    digest.total_collected = 100
    digest.total_after_dedupe = 60
    return digest


def test_html_contains_all_parts():
    html = render_html(build_digest())
    for expected in ["法学トピック", "実務上の意味", "経済トピック", "注目点1",
                     "https://example.com/a", "2026年09月16日"]:
        assert expected in html


def test_html_escapes_untrusted_feed_content():
    """フィード由来の見出しはそのままHTMLに入るため、必ずエスケープされること。"""
    digest = build_digest()
    digest.legal_items[0].title = '<script>alert("xss")</script>'
    digest.legal_items[0].summary = "5 < 10 & 10 > 5"
    digest.legal_items[0].articles[0].url = 'https://x/"><script>alert(1)</script>'

    html = render_html(digest)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "5 &lt; 10 &amp; 10 &gt; 5" in html
    # 属性からの脱出も防げていること
    assert '"><script>' not in html


def test_markdown_and_text_render():
    digest = build_digest()
    markdown = render_markdown(digest)
    assert "# 2026年09月16日 ニュースダイジェスト" in markdown
    assert "**実務上の意味**" in markdown
    assert "[出典A](https://example.com/a)" in markdown

    text = render_text(digest)
    assert "法学・司法［重点］" in text
    assert "https://example.com/a" in text


def test_slack_uses_mrkdwn_links():
    slack = render_slack(build_digest())
    assert "<https://example.com/a|法学トピック>" in slack


def test_empty_legal_section_has_placeholder():
    digest = build_digest()
    digest.legal_items = []
    assert "本日該当する記事はありませんでした" in render_html(digest)
