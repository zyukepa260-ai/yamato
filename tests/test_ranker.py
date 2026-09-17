from datetime import datetime, timedelta, timezone

from newsdigest.models import Article
from newsdigest.ranker import legal_relevance, recency_factor, score_articles, select

NOW = datetime(2026, 9, 16, 0, 0, tzinfo=timezone.utc)


def make(title, category="社会", weight=1.0, hours_ago=1, summary=""):
    return Article(
        title=title, url=f"https://x/{abs(hash(title))}", source="S",
        category=category, summary=summary, source_weight=weight,
        published=NOW - timedelta(hours=hours_ago),
    )


def test_legal_terms_score_above_non_legal():
    legal, _ = legal_relevance("最高裁が違憲判断、法改正へ")
    plain, _ = legal_relevance("今日の天気は晴れ")
    assert legal > 10
    assert plain == 0


def test_overlapping_terms_are_not_double_counted():
    """「最高裁」を「高裁」として、「個人情報保護法」を「個人情報」として重複計上しない。"""
    top, top_terms = legal_relevance("最高裁")
    lower, _ = legal_relevance("高裁")
    assert "高裁" not in top_terms
    assert top == 3.0 * 2      # 最高裁(3.0) × 見出し倍率(2.0)
    assert lower == 2.0 * 2    # 高裁(2.0) × 見出し倍率(2.0)

    _, terms = legal_relevance("個人情報保護法")
    assert terms == ["個人情報保護法"]


def test_english_matching_respects_word_boundaries():
    score, _ = legal_relevance("The lawn mower flaw")
    assert score == 0


def test_title_hits_weigh_more_than_body():
    title_hit, _ = legal_relevance("最高裁", "")
    body_hit, _ = legal_relevance("", "最高裁")
    assert title_hit == body_hit * 2


def test_recency_factor_decays():
    assert recency_factor(NOW, NOW, 24) == 1.0
    assert recency_factor(NOW - timedelta(hours=24), NOW, 24) == 0.0
    assert recency_factor(None, NOW, 24) == 0.5   # 日時不明は中間値


def test_legal_article_outranks_plain_article():
    legal = make("最高裁が違憲判断、法改正へ", category="法学・司法", weight=2.0)
    plain = make("今日の天気は晴れ", category="社会", weight=1.0)
    ranked = score_articles([plain, legal], now=NOW)
    assert ranked[0] is legal


def test_select_guarantees_legal_quota():
    """一般記事が大量にあっても法学枠は確保される。"""
    legal = [make(f"最高裁の判決{i}について", category="法学・司法", weight=2.0) for i in range(10)]
    plain = [make(f"日常のニュース{i}です", category="社会") for i in range(100)]
    scored = score_articles(legal + plain, now=NOW)
    chosen = select(scored, limit=20, legal_min=8)
    legal_chosen = [a for a in chosen if a.category == "法学・司法"]
    assert len(legal_chosen) >= 8


def test_select_caps_single_category():
    """1分野が枠を占有しないこと。"""
    flood = [make(f"社会の話題{i}です", category="社会") for i in range(60)]
    other = [make(f"経済の話題{i}です", category="経済・ビジネス") for i in range(20)]
    scored = score_articles(flood + other, now=NOW)
    chosen = select(scored, limit=50, legal_min=0, per_category_cap=18)
    assert sum(1 for a in chosen if a.category == "社会") <= 18
