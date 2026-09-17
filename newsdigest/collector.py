"""RSS/Atom フィードを並列取得して Article に変換する。

方針: 1つのフィードが落ちていても全体は止めない。失敗は記録して次に進む。
"""

from __future__ import annotations

import calendar
import concurrent.futures as futures
import html
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

from .models import Article
from .sources import FeedSpec

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; yamato-news-digest/1.0; +https://github.com/)"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Googleニュースの見出し末尾に付く " - 媒体名" を落とすための正規表現
_GNEWS_SUFFIX_RE = re.compile(r"\s+-\s+[^-]{2,40}$")


def strip_html(text: str, limit: int = 400) -> str:
    """HTMLタグを除去して1行のプレーンテキストにする。"""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _parse_published(entry) -> datetime | None:
    """feedparser のエントリから UTC の datetime を取り出す。"""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if value:
            try:
                return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _clean_title(title: str, kind: str) -> str:
    title = strip_html(title, limit=300)
    if kind == "google_news":
        title = _GNEWS_SUFFIX_RE.sub("", title).strip()
    return title


class FetchResult:
    """1フィードの取得結果。"""

    def __init__(self, spec: FeedSpec, articles: list[Article], error: str | None = None):
        self.spec = spec
        self.articles = articles
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.articles)


def _read_feed(spec: FeedSpec):
    """フィードを取得してパースする。

    feedparser.parse() はタイムアウトを受け付けないため、URLの場合は自前で
    取得してからパースする。応答の無いフィードが1つあるだけで配信全体が
    遅れるのを防ぐための措置。
    （テストではRSS文字列を直接渡せるよう、URL以外はそのまま委譲する）
    """
    if not spec.url.lower().startswith(("http://", "https://")):
        return feedparser.parse(spec.url, agent=USER_AGENT)

    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=spec.timeout) as response:
        payload = response.read()
    return feedparser.parse(payload)


def fetch_feed(spec: FeedSpec) -> FetchResult:
    """1フィードを取得して Article のリストを返す。例外は握りつぶして記録する。"""
    try:
        parsed = _read_feed(spec)
    except urllib.error.HTTPError as exc:
        return FetchResult(spec, [], error=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:  # タイムアウト・DNS・パーサ由来の想定外エラー
        logger.warning("取得失敗 %s: %r", spec.name, exc)
        return FetchResult(spec, [], error=f"{type(exc).__name__}: {exc}")

    status = getattr(parsed, "status", None)
    entries = getattr(parsed, "entries", []) or []

    if not entries:
        reason = getattr(parsed, "bozo_exception", None)
        detail = f"HTTP {status}" if status else (repr(reason) if reason else "エントリ0件")
        logger.warning("記事なし %s (%s)", spec.name, detail)
        return FetchResult(spec, [], error=detail)

    articles: list[Article] = []
    for entry in entries[: spec.max_entries]:
        link = (entry.get("link") or "").strip()
        title = _clean_title(entry.get("title") or "", spec.kind)
        if not link or not title:
            continue
        raw_summary = entry.get("summary") or entry.get("description") or ""
        articles.append(
            Article(
                title=title,
                url=link,
                source=spec.name,
                category=spec.category,
                summary=strip_html(raw_summary),
                published=_parse_published(entry),
                source_weight=spec.weight,
            )
        )

    return FetchResult(spec, articles)


def collect(
    specs: list[FeedSpec],
    lookback_hours: int = 24,
    max_workers: int = 12,
    now: datetime | None = None,
) -> tuple[list[Article], list[str]]:
    """全フィードを並列取得する。

    Returns:
        (記事リスト, 失敗したフィード名のリスト)

    公開日時が不明な記事は「新しいかもしれない」ものとして残す。
    lookback より古いと確実に分かる記事だけを捨てる。
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)

    articles: list[Article] = []
    failed: list[str] = []

    with futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for result in pool.map(fetch_feed, specs):
            if result.error:
                failed.append(f"{result.spec.name} ({result.error})")
                continue
            for article in result.articles:
                if article.published and article.published < cutoff:
                    continue
                articles.append(article)

    logger.info("収集: %d件 / 失敗フィード: %d件", len(articles), len(failed))
    return articles, failed
