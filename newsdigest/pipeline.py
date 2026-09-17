"""収集から配信までの一連の流れ。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import archive as archive_module
from .collector import collect
from .config import Settings, load_sources_config
from .dedupe import deduplicate
from .models import Digest
from .notifiers import DeliveryResult, build_notifiers
from .ranker import score_articles, select
from .sources import build_feed_specs
from .summarizer import summarize

logger = logging.getLogger(__name__)


@dataclass
class RunReport:
    digest: Digest
    deliveries: list[DeliveryResult] = field(default_factory=list)
    archive_path: str = ""

    @property
    def delivered(self) -> bool:
        """1つでも配信に成功したか。"""
        return any(d.ok for d in self.deliveries)


def build_digest(settings: Settings, now: datetime | None = None) -> Digest:
    """収集〜要約までを実行して Digest を返す（配信は行わない）。"""
    now_utc = now or datetime.now(timezone.utc)
    local_now = now_utc.astimezone(settings.tz)

    config = load_sources_config(settings.sources_path)
    specs = build_feed_specs(config)
    logger.info("フィード %d件から収集します", len(specs))

    raw_articles, failed = collect(
        specs, lookback_hours=settings.lookback_hours, now=now_utc
    )
    total_collected = len(raw_articles)

    unique_articles = deduplicate(raw_articles)
    logger.info("重複除去: %d件 -> %d件", total_collected, len(unique_articles))

    scored = score_articles(
        unique_articles, now=now_utc, lookback_hours=settings.lookback_hours
    )
    selected = select(scored, limit=settings.max_articles, legal_min=settings.legal_min)
    logger.info("LLMに渡す記事: %d件", len(selected))

    digest = summarize(
        selected,
        generated_at=local_now,
        api_key=settings.anthropic_api_key,
        model=settings.model,
        legal_min=settings.legal_min,
        date_label=local_now.strftime("%Y年%m月%d日"),
    )
    digest.total_collected = total_collected
    digest.total_after_dedupe = len(unique_articles)
    digest.total_sources = len(specs)
    digest.failed_sources = failed
    return digest


def run(settings: Settings, now: datetime | None = None, deliver: bool = True) -> RunReport:
    """ダイジェストを生成し、設定されたチャネルへ配信する。"""
    digest = build_digest(settings, now=now)
    report = RunReport(digest=digest)

    try:
        report.archive_path = str(archive_module.save(digest, settings.archive_dir))
    except OSError as exc:
        logger.warning("アーカイブ保存に失敗しました: %r", exc)

    if not deliver:
        return report

    for notifier in build_notifiers(settings):
        result = notifier.send(digest)
        report.deliveries.append(result)
        if result.ok:
            logger.info("配信成功 [%s] %s", result.channel, result.detail)
        else:
            logger.error("配信失敗 [%s] %s", result.channel, result.detail)

    return report
