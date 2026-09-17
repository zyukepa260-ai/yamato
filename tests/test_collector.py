import feedparser

from newsdigest.collector import _clean_title, _parse_published, fetch_feed, strip_html
from newsdigest.sources import FeedSpec

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>テストフィード</title>
<item>
  <title>最高裁 判決 &amp; その影響</title>
  <link>https://example.com/a</link>
  <description>&lt;p&gt;本文のテスト&lt;/p&gt;</description>
  <pubDate>Tue, 15 Sep 2026 23:10:00 GMT</pubDate>
</item>
<item><title>リンクなし</title><link></link></item>
</channel></rss>"""


def test_strip_html_unescapes_and_collapses():
    assert strip_html("<p>Hello &amp; <b>world</b>   test</p>") == "Hello & world test"


def test_strip_html_truncates():
    assert strip_html("a" * 500, limit=100).endswith("…")


def test_google_news_suffix_removed_only_for_google():
    assert _clean_title("最高裁が判断 - 日本経済新聞", "google_news") == "最高裁が判断"
    assert _clean_title("最高裁が判断 - 日本経済新聞", "rss") == "最高裁が判断 - 日本経済新聞"


def test_parse_published_returns_utc():
    entry = feedparser.parse(RSS).entries[0]
    published = _parse_published(entry)
    assert published is not None
    assert published.tzinfo is not None
    assert published.year == 2026


def test_parse_published_handles_missing_date():
    assert _parse_published(feedparser.parse(RSS).entries[1]) is None


def test_fetch_feed_skips_entries_without_link():
    spec = FeedSpec(name="t", url=RSS, category="法学・司法", weight=2.0)
    result = fetch_feed(spec)
    assert result.ok
    assert len(result.articles) == 1
    article = result.articles[0]
    assert article.title == "最高裁 判決 & その影響"
    assert article.summary == "本文のテスト"
    assert article.source_weight == 2.0


def test_fetch_feed_reports_error_instead_of_raising():
    spec = FeedSpec(name="broken", url="これはフィードではない", category="社会")
    result = fetch_feed(spec)
    assert not result.ok
    assert result.error
