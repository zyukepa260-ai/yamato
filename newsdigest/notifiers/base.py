"""通知チャネルの共通インターフェース。"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Digest


@dataclass
class DeliveryResult:
    channel: str
    ok: bool
    detail: str = ""


class Notifier:
    """配信チャネルの基底クラス。"""

    name = "base"

    def available(self) -> tuple[bool, str]:
        """設定が揃っているかを返す。(利用可否, 理由)"""
        raise NotImplementedError

    def send(self, digest: Digest) -> DeliveryResult:
        raise NotImplementedError
