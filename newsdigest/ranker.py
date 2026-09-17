"""記事のスコアリングと選抜。

法学関連を重点的に扱うため、法律用語にマッチした記事へ大きな加点を行い、
さらに選抜時に法学枠を確保する。
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .models import Article

LEGAL_CATEGORY = "法学・司法"

# ---------------------------------------------------------------------------
# 法律用語の重み付け辞書
#   日本語は部分一致、英語は単語境界つき正規表現で判定する。
# ---------------------------------------------------------------------------
LEGAL_TERMS_JA: dict[str, float] = {
    # 最重要（司法判断・法改正そのもの）
    "最高裁": 3.0, "大法廷": 3.0, "違憲": 3.0, "合憲": 2.5, "判例": 3.0,
    "法改正": 3.0, "改正法": 3.0, "判示": 2.5, "憲法": 2.5,
    # 重要（訴訟・立法プロセス）
    "判決": 2.0, "高裁": 2.0, "地裁": 2.0, "家裁": 2.0, "簡裁": 1.5,
    "訴訟": 2.0, "提訴": 2.0, "上告": 2.0, "控訴": 2.0, "決定要旨": 2.0,
    "法案": 2.0, "可決": 1.5, "施行": 2.0, "条例": 2.0, "省令": 2.0, "政令": 2.0,
    "民法": 2.5, "刑法": 2.5, "商法": 2.5, "会社法": 2.5, "民事訴訟法": 2.5,
    "刑事訴訟法": 2.5, "独占禁止法": 2.5, "個人情報保護法": 2.5,
    "労働基準法": 2.5, "著作権法": 2.5, "特許法": 2.5, "行政法": 2.0,
    # 関連（実務・制度）
    "弁護士": 1.0, "検察": 1.0, "起訴": 1.5, "不起訴": 1.5, "損害賠償": 1.5,
    "差止": 1.5, "仮処分": 1.5, "和解": 1.0, "審決": 1.5, "課徴金": 1.5,
    "規制": 1.0, "ガイドライン": 1.0, "コンプライアンス": 1.0, "内部統制": 1.0,
    "知的財産": 1.5, "著作権": 1.2, "特許": 1.0, "商標": 1.0, "契約": 0.8,
    "法務": 1.2, "司法": 1.2, "裁判": 1.5, "立法": 1.5, "法令": 1.5,
    "パブリックコメント": 1.5, "公正取引委員会": 2.0, "個人情報": 1.0,
    "プライバシー": 1.0, "権利侵害": 1.5, "法的": 1.0,
}

LEGAL_TERMS_EN: dict[str, float] = {
    "supreme court": 3.0, "unconstitutional": 3.0, "constitutional": 2.0,
    "ruling": 2.0, "verdict": 2.0, "court": 1.5, "lawsuit": 2.0,
    "litigation": 2.0, "statute": 2.0, "legislation": 2.0, "antitrust": 2.0,
    "gdpr": 2.0, "injunction": 2.0, "plaintiff": 2.0, "defendant": 2.0,
    "regulation": 1.0, "copyright": 1.2, "patent": 1.0, "trademark": 1.0,
    "privacy": 1.0, "compliance": 1.0, "appeal": 1.0, "attorney": 1.0,
    "prosecutor": 1.0, "settlement": 1.0, "legal": 1.0, "law": 1.0,
}

_EN_PATTERNS = {
    term: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    for term in LEGAL_TERMS_EN
}

# 見出しでのヒットは本文よりも強いシグナルとして扱う
TITLE_MULTIPLIER = 2.0
BODY_MULTIPLIER = 1.0


# 長い用語から先に照合するための順序（「最高裁」を「高裁」として二重計上しないため）
_JA_TERMS_BY_LENGTH = sorted(LEGAL_TERMS_JA.items(), key=lambda kv: len(kv[0]), reverse=True)
_EN_TERMS_BY_LENGTH = sorted(LEGAL_TERMS_EN.items(), key=lambda kv: len(kv[0]), reverse=True)


def _scan_field(field: str, multiplier: float) -> tuple[float, list[str]]:
    """1つのテキストを走査する。

    長い用語を優先して照合し、一致した範囲をマスクすることで
    「最高裁」と「高裁」、「個人情報保護法」と「個人情報」のような
    包含関係にある用語の二重計上を防ぐ。
    """
    score = 0.0
    matched: list[str] = []
    consumed = [False] * len(field)

    def claim(start: int, end: int) -> bool:
        if any(consumed[start:end]):
            return False
        for i in range(start, end):
            consumed[i] = True
        return True

    for term, weight in _JA_TERMS_BY_LENGTH:
        start = field.find(term)
        while start != -1:
            if claim(start, start + len(term)):
                score += weight * multiplier
                if term not in matched:
                    matched.append(term)
            start = field.find(term, start + 1)

    for term, weight in _EN_TERMS_BY_LENGTH:
        for match in _EN_PATTERNS[term].finditer(field):
            if claim(match.start(), match.end()):
                score += weight * multiplier
                if term not in matched:
                    matched.append(term)

    return score, matched


def legal_relevance(title: str, body: str = "") -> tuple[float, list[str]]:
    """法学関連度のスコアと、ヒットした用語を返す。

    見出しでのヒットは本文よりも強いシグナルとして重み付けする。
    """
    score = 0.0
    matched: list[str] = []

    for field, multiplier in ((title, TITLE_MULTIPLIER), (body, BODY_MULTIPLIER)):
        if not field:
            continue
        field_score, field_matched = _scan_field(field, multiplier)
        score += field_score
        for term in field_matched:
            if term not in matched:
                matched.append(term)

    return score, matched


def recency_factor(published: datetime | None, now: datetime, lookback_hours: int) -> float:
    """新しいほど1.0に近づく係数（0.0〜1.0）。日時不明は中間値を与える。"""
    if published is None:
        return 0.5
    age_hours = (now - published).total_seconds() / 3600.0
    if age_hours < 0:
        return 1.0
    if age_hours >= lookback_hours:
        return 0.0
    return 1.0 - (age_hours / lookback_hours)


def score_articles(
    articles: list[Article],
    now: datetime | None = None,
    lookback_hours: int = 24,
) -> list[Article]:
    """各記事にスコアを付与して、降順に並べ替えて返す。"""
    now = now or datetime.now(timezone.utc)

    for article in articles:
        legal, matched = legal_relevance(article.title, article.summary)
        article.legal_score = legal
        article.matched_terms = matched[:8]

        recency = recency_factor(article.published, now, lookback_hours)
        # 複数媒体が報じた話題ほど重要とみなす（対数で頭打ちさせる）
        coverage = math.log1p(article.duplicate_count) * 1.2

        article.score = (
            article.source_weight * 1.0
            + recency * 1.5
            + coverage
            + legal * 1.5
        )

    return sorted(articles, key=lambda a: a.score, reverse=True)


def select(
    articles: list[Article],
    limit: int = 140,
    legal_min: int = 8,
    per_category_cap: int = 18,
) -> list[Article]:
    """LLMに渡す記事を選抜する。

    - 法学関連は最低 `legal_min` 件を必ず確保する
    - 1分野が枠を占有しないよう `per_category_cap` で上限を設ける
    """
    ranked = sorted(articles, key=lambda a: a.score, reverse=True)

    legal_pool = [a for a in ranked if a.category == LEGAL_CATEGORY or a.legal_score >= 2.0]
    selected: list[Article] = []
    chosen: set[int] = set()

    # 1) 法学枠を先に確保
    for article in legal_pool[:legal_min]:
        selected.append(article)
        chosen.add(id(article))

    # 2) 残りを分野バランスを見ながら埋める
    counts: dict[str, int] = {}
    for article in selected:
        counts[article.category] = counts.get(article.category, 0) + 1

    for article in ranked:
        if len(selected) >= limit:
            break
        if id(article) in chosen:
            continue
        count = counts.get(article.category, 0)
        # 法学は重点分野なので上限を緩める
        cap = per_category_cap * 2 if article.category == LEGAL_CATEGORY else per_category_cap
        if count >= cap:
            continue
        selected.append(article)
        chosen.add(id(article))
        counts[article.category] = count + 1

    return selected
