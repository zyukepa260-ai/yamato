import json
import re
from datetime import datetime, timezone

from newsdigest.dashboard import render_dashboard
from newsdigest.models import Article, Digest, DigestItem, DigestSection

NOW = datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc)


def build(**overrides) -> Digest:
    article = Article(title="記事", url="https://example.com/a", source="出典A",
                      category="法学・司法")
    digest = Digest(generated_at=NOW, engine="claude", headline="今日の概況")
    digest.legal_items = [
        DigestItem(title="法学トピック", summary="要約本文", significance="実務上の意味",
                   tags=["個人情報"], articles=[article])
    ]
    digest.sections = [
        DigestSection(category="経済・ビジネス",
                      items=[DigestItem(title="経済トピック", summary="要約",
                                        articles=[article])])
    ]
    digest.watchlist = ["注目点1"]
    digest.total_collected = 312
    digest.total_after_dedupe = 187
    digest.total_sources = 43
    for key, value in overrides.items():
        setattr(digest, key, value)
    return digest


def payload_of(html: str) -> dict:
    """埋め込まれたJSONデータを取り出す。"""
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                      html, re.S)
    assert match, "データブロックが見つからない"
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_dashboard_is_self_contained():
    """外部CDNに依存せず、ファイル単体で開けること。"""
    html = render_dashboard(build())
    assert "<script" in html
    # 外部スクリプト・スタイルの読み込みが無い
    assert "src=\"http" not in html
    assert "<link" not in html
    assert "cdn" not in html.lower()


def test_dashboard_contains_headline_and_stats():
    html = render_dashboard(build())
    for expected in ["2026年09月17日", "今日の概況", "312", "187", "43"]:
        assert expected in html


def test_payload_marks_legal_group_as_emphasis():
    data = payload_of(render_dashboard(build()))
    legal = data["groups"][0]
    assert legal["category"] == "法学・司法"
    assert legal["emphasis"] is True
    assert legal["items"][0]["significance"] == "実務上の意味"
    assert legal["items"][0]["sources"][0]["url"] == "https://example.com/a"
    # 法学以外は強調しない
    assert data["groups"][1]["emphasis"] is False


def test_script_injection_from_feed_is_neutralised():
    """記事タイトルはフィード由来の外部入力。scriptタグを閉じさせないこと。"""
    digest = build()
    digest.legal_items[0].title = '</script><script>alert("xss")</script>'
    digest.headline = '<img src=x onerror=alert(1)>'

    html = render_dashboard(digest)

    # (1) 埋め込みJSONから抜け出せない（</script> が実体として現れない）
    assert "</script><script>alert" not in html
    assert "<\\/script>" in html

    # (2) マークアップとして書き出す箇所は必ずエスケープされている。
    #     JSONデータ部は <script type="application/json"> 内の不活性テキストであり、
    #     DOM構築は textContent のみで行うため、生の文字列が残っていてよい。
    markup = re.sub(r'<script id="data".*?</script>', "", html, flags=re.S)
    assert "<img src=x" not in markup
    assert "&lt;img src=x" in markup

    # (3) データとしては元の文字列を正しく復元できる
    data = payload_of(html)
    assert data["groups"][0]["items"][0]["title"] == '</script><script>alert("xss")</script>'


def test_dom_is_built_without_innerhtml():
    """値の描画に innerHTML を使っていないこと（使うとXSS経路になる）。"""
    html = render_dashboard(build())
    assert "innerHTML" not in html


def test_failed_sources_are_listed_and_counted():
    digest = build(failed_sources=["壊れたフィード (HTTP 404)", "別のフィード (timeout)"])
    html = render_dashboard(digest)
    assert "取得できなかった情報源 2件" in html
    assert "壊れたフィード (HTTP 404)" in html
    # 43件中2件失敗 → 41/43
    assert "41" in html


def test_healthy_sources_show_ok_status():
    html = render_dashboard(build())
    assert 'class="badge status ok"' in html
    assert "43/43" in html


def test_empty_digest_does_not_crash():
    empty = Digest(generated_at=NOW, engine="fallback", headline="対象記事なし")
    html = render_dashboard(empty)
    assert "対象記事なし" in html
    assert payload_of(html)["groups"] == []


def test_dark_mode_is_declared_for_both_scopes():
    """OS設定とテーマ切替の両方でダークが効くこと。"""
    html = render_dashboard(build())
    assert "@media (prefers-color-scheme: dark)" in html
    assert ':root[data-theme="dark"]' in html
    assert ':root:not([data-theme="light"])' in html
