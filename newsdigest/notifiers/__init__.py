"""配信チャネルの生成。"""

from __future__ import annotations

import logging

from ..config import Settings
from .base import DeliveryResult, Notifier
from .localfile import FileNotifier
from .mail import MailNotifier
from .webhook import DiscordNotifier, SlackNotifier

logger = logging.getLogger(__name__)

__all__ = [
    "DeliveryResult",
    "Notifier",
    "FileNotifier",
    "MailNotifier",
    "SlackNotifier",
    "DiscordNotifier",
    "build_notifiers",
]


def build_notifiers(settings: Settings) -> list[Notifier]:
    """設定で指定されたチャネルのみを組み立てる。"""
    registry = {
        "email": lambda: MailNotifier(settings.mail),
        "mail": lambda: MailNotifier(settings.mail),
        "slack": lambda: SlackNotifier(settings.slack_webhook),
        "discord": lambda: DiscordNotifier(settings.discord_webhook),
        "file": lambda: FileNotifier(settings.archive_dir),
    }

    notifiers: list[Notifier] = []
    for name in settings.notifiers:
        factory = registry.get(name.strip().lower())
        if factory is None:
            logger.warning("未知の配信チャネルを無視します: %s", name)
            continue
        notifiers.append(factory())
    return notifiers
