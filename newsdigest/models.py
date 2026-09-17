"""パイプライン全体で受け渡しするデータ構造。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Article:
    """収集した記事1件。"""

    title: str
    url: str
    source: str
    category: str
    summary: str = ""
    published: datetime | None = None
    source_weight: float = 1.0

    # 重複排除・ランキング時に算出される
    duplicate_count: int = 1   # 同じ話題を報じた媒体数（多いほど注目度が高い）
    score: float = 0.0
    legal_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)

    @property
    def is_legal(self) -> bool:
        """法学セクションに載せる候補かどうか。"""
        return self.category == "法学・司法" or self.legal_score > 0

    @property
    def fingerprint(self) -> str:
        """重複判定用の安定したID。"""
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "summary": self.summary,
            "published": self.published.isoformat() if self.published else None,
            "duplicate_count": self.duplicate_count,
            "score": round(self.score, 3),
            "legal_score": round(self.legal_score, 3),
            "matched_terms": self.matched_terms,
        }


@dataclass
class DigestItem:
    """ダイジェスト内の1トピック（複数記事をまとめたもの）。"""

    title: str
    summary: str
    articles: list[Article] = field(default_factory=list)
    significance: str = ""   # 法学セクションのみ: 実務上の意味
    tags: list[str] = field(default_factory=list)


@dataclass
class DigestSection:
    """分野ごとのまとまり。"""

    category: str
    items: list[DigestItem] = field(default_factory=list)


@dataclass
class Digest:
    """1回分の配信内容すべて。"""

    generated_at: datetime
    headline: str = ""
    legal_items: list[DigestItem] = field(default_factory=list)
    sections: list[DigestSection] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=list)

    # メタ情報
    total_collected: int = 0
    total_after_dedupe: int = 0
    total_sources: int = 0              # 取得を試みたフィード総数
    failed_sources: list[str] = field(default_factory=list)
    engine: str = "claude"   # "claude" か "fallback"

    @property
    def date_label(self) -> str:
        return self.generated_at.strftime("%Y年%m月%d日")

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "headline": self.headline,
            "engine": self.engine,
            "legal_items": [
                {
                    "title": i.title,
                    "summary": i.summary,
                    "significance": i.significance,
                    "tags": i.tags,
                    "articles": [a.to_dict() for a in i.articles],
                }
                for i in self.legal_items
            ],
            "sections": [
                {
                    "category": s.category,
                    "items": [
                        {
                            "title": i.title,
                            "summary": i.summary,
                            "articles": [a.to_dict() for a in i.articles],
                        }
                        for i in s.items
                    ],
                }
                for s in self.sections
            ],
            "watchlist": self.watchlist,
            "stats": {
                "total_collected": self.total_collected,
                "total_after_dedupe": self.total_after_dedupe,
                "total_sources": self.total_sources,
                "failed_sources": self.failed_sources,
            },
        }
