"""Slack / Discord の Incoming Webhook への配信。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..models import Digest
from ..render import render_slack
from .base import DeliveryResult, Notifier

TIMEOUT = 20
# Discord のメッセージ上限は2000文字
DISCORD_LIMIT = 1900


def _post_json(url: str, payload: dict) -> tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return 200 <= response.status < 300, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


class SlackNotifier(Notifier):
    name = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def available(self) -> tuple[bool, str]:
        if not self.webhook_url:
            return False, "未設定: SLACK_WEBHOOK_URL"
        return True, ""

    def send(self, digest: Digest) -> DeliveryResult:
        ok, reason = self.available()
        if not ok:
            return DeliveryResult(self.name, False, reason)
        sent, detail = _post_json(self.webhook_url, {"text": render_slack(digest)})
        return DeliveryResult(self.name, sent, detail)


class DiscordNotifier(Notifier):
    name = "discord"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def available(self) -> tuple[bool, str]:
        if not self.webhook_url:
            return False, "未設定: DISCORD_WEBHOOK_URL"
        return True, ""

    def send(self, digest: Digest) -> DeliveryResult:
        ok, reason = self.available()
        if not ok:
            return DeliveryResult(self.name, False, reason)
        content = render_slack(digest)
        if len(content) > DISCORD_LIMIT:
            content = content[:DISCORD_LIMIT] + "\n…（以下省略）"
        sent, detail = _post_json(self.webhook_url, {"content": content})
        return DeliveryResult(self.name, sent, detail)
