#!/usr/bin/env python3
"""自分のPC・サーバーで毎朝8時に実行するための常駐スクリプト。

GitHub Actions を使わない場合の選択肢です。
cron や launchd、タスクスケジューラが使えるなら、そちらの方が確実です。

    python scripts/run_local_scheduler.py            # 毎日8:00に実行
    python scripts/run_local_scheduler.py --at 07:30 # 時刻を変える
    python scripts/run_local_scheduler.py --once     # 今すぐ1回だけ実行
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsdigest.cli import setup_logging          # noqa: E402
from newsdigest.config import Settings            # noqa: E402
from newsdigest.pipeline import run               # noqa: E402

logger = logging.getLogger("scheduler")


def next_run_at(target_hour: int, target_minute: int, tz) -> datetime:
    now = datetime.now(tz)
    candidate = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def execute(settings: Settings) -> None:
    try:
        report = run(settings)
        for result in report.deliveries:
            level = logging.INFO if result.ok else logging.ERROR
            logger.log(level, "[%s] %s", result.channel, result.detail)
    except Exception:
        # 1日失敗しても常駐は止めない
        logger.exception("ダイジェスト生成に失敗しました。次回の実行まで待機します。")


def main() -> int:
    parser = argparse.ArgumentParser(description="毎朝定時にダイジェストを配信する常駐スクリプト")
    parser.add_argument("--at", default="08:00", help="実行時刻 HH:MM（既定 08:00）")
    parser.add_argument("--once", action="store_true", help="待機せず今すぐ1回だけ実行")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    settings = Settings.from_env()

    if args.once:
        execute(settings)
        return 0

    try:
        hour, minute = (int(part) for part in args.at.split(":", 1))
    except ValueError:
        parser.error("--at は HH:MM 形式で指定してください（例: 08:00）")

    logger.info("スケジューラを開始しました（毎日 %02d:%02d / %s）", hour, minute, settings.timezone_name)
    while True:
        target = next_run_at(hour, minute, settings.tz)
        wait_seconds = (target - datetime.now(settings.tz)).total_seconds()
        logger.info("次回実行: %s（約%.1f時間後）", target.strftime("%Y-%m-%d %H:%M"), wait_seconds / 3600)
        time.sleep(max(wait_seconds, 1))
        execute(settings)
        # 同じ時刻で二重実行しないよう少し進めてから次のループへ
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
