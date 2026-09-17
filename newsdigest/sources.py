"""sources.yaml から実際に取得するフィード一覧を組み立てる。"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any

GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search"


@dataclass
class FeedSpec:
    """取得対象のフィード1件。"""

    name: str
    url: str
    category: str
    weight: float = 1.0
    kind: str = "rss"          # "rss" か "google_news"
    max_entries: int = 30
    timeout: int = 20


def build_google_news_url(
    query: str, hl: str = "ja", gl: str = "JP", ceid: str = "JP:ja", recency: str = "when:2d"
) -> str:
    """Googleニュース検索のRSS URLを組み立てる。

    `recency` は Google ニュースの検索演算子（例: when:1d, when:7d）。
    空文字を渡すと期間指定なしになる。
    """
    full_query = f"{query} {recency}".strip() if recency else query
    params = urllib.parse.urlencode(
        {"q": full_query, "hl": hl, "gl": gl, "ceid": ceid}
    )
    return f"{GOOGLE_NEWS_SEARCH}?{params}"


def build_feed_specs(config: dict[str, Any]) -> list[FeedSpec]:
    """設定辞書から FeedSpec のリストを作る（enabled: false は除外）。"""
    defaults = config.get("defaults") or {}
    default_timeout = int(defaults.get("timeout", 20))
    default_max = int(defaults.get("max_entries_per_feed", 30))

    specs: list[FeedSpec] = []

    # --- 個別RSS ---
    for raw in config.get("feeds") or []:
        if not raw or not raw.get("url"):
            continue
        if raw.get("enabled", True) is False:
            continue
        specs.append(
            FeedSpec(
                name=raw.get("name") or raw["url"],
                url=raw["url"],
                category=raw.get("category", "その他"),
                weight=float(raw.get("weight", 1.0)),
                kind="rss",
                max_entries=int(raw.get("max_entries", default_max)),
                timeout=int(raw.get("timeout", default_timeout)),
            )
        )

    # --- Googleニュース検索 ---
    gnews = config.get("google_news") or {}
    if gnews.get("enabled", False):
        hl = gnews.get("hl", "ja")
        gl = gnews.get("gl", "JP")
        ceid = gnews.get("ceid", "JP:ja")
        recency = gnews.get("recency", "when:2d")
        for raw in gnews.get("queries") or []:
            if not raw or not raw.get("q"):
                continue
            if raw.get("enabled", True) is False:
                continue
            specs.append(
                FeedSpec(
                    name=f"Google:{raw.get('name') or raw['q']}",
                    url=build_google_news_url(raw["q"], hl, gl, ceid, recency),
                    category=raw.get("category", "その他"),
                    weight=float(raw.get("weight", 1.0)),
                    kind="google_news",
                    max_entries=int(raw.get("max_entries", default_max)),
                    timeout=int(raw.get("timeout", default_timeout)),
                )
            )

    return specs
