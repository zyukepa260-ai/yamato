from newsdigest.dedupe import (
    _bigrams,
    deduplicate,
    is_similar,
    normalize_title,
    normalize_url,
)
from newsdigest.models import Article


def make(title, url, weight=1.0, summary=""):
    return Article(
        title=title, url=url, source="S", category="社会",
        source_weight=weight, summary=summary,
    )


def test_normalize_url_strips_tracking_and_case():
    assert normalize_url("https://WWW.Example.com/a/?utm_source=x&id=3#frag") == (
        "https://example.com/a?id=3"
    )


def test_normalize_url_keeps_meaningful_query():
    assert "id=3" in normalize_url("https://example.com/a?id=3")


def sim(a, b):
    return is_similar(_bigrams(normalize_title(a)), _bigrams(normalize_title(b)))


def test_paraphrased_headlines_are_duplicates():
    assert sim("最高裁、選択的夫婦別姓めぐり判断", "最高裁が選択的夫婦別姓をめぐり判断を示す")
    assert sim("改正個人情報保護法が施行", "改正個人情報保護法、4月1日に施行")
    assert sim("Supreme Court rules on privacy case", "Supreme Court issues ruling in privacy case")


def test_different_stories_are_not_duplicates():
    # 裁判所が違えば別ニュース
    assert not sim("東京地裁、賠償命令", "大阪地裁、賠償命令")
    assert not sim("阪神が優勝", "巨人が優勝")
    assert not sim("今日の天気は晴れ", "最高裁、選択的夫婦別姓めぐり判断")


def test_duplicate_urls_are_merged_with_count():
    articles = [
        make("同じ記事", "https://a.com/1"),
        make("同じ記事", "https://a.com/1?utm_source=z"),
    ]
    result = deduplicate(articles)
    assert len(result) == 1
    assert result[0].duplicate_count == 2


def test_primary_source_wins_on_duplicate():
    """一次情報（重み高）が残ることを確認する。"""
    articles = [
        make("最高裁が判断を示した", "https://news.com/1", weight=1.0),
        make("最高裁が判断を示したと報じられた", "https://courts.go.jp/1", weight=2.6),
    ]
    result = deduplicate(articles)
    assert len(result) == 1
    assert result[0].source_weight == 2.6
    assert result[0].duplicate_count == 2


def test_unrelated_articles_survive():
    articles = [make("天気", "https://a/1"), make("経済", "https://b/2"), make("科学", "https://c/3")]
    assert len(deduplicate(articles)) == 3
