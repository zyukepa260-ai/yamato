"""環境変数と sources.yaml から設定を読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = PROJECT_ROOT / "config" / "sources.yaml"
DEFAULT_ARCHIVE = PROJECT_ROOT / "archive"

# tzdata が無い環境（Windows等）でも +09:00 で動くようにするためのフォールバック
_JST_FALLBACK = timezone(timedelta(hours=9), "JST")


def load_tz(name: str):
    """タイムゾーンを取得する。取得できなければ JST 固定オフセットを返す。"""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return _JST_FALLBACK


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(key: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return list(default or [])
    return [part.strip() for part in raw.split(",") if part.strip()]


def load_dotenv(path: Path | None = None) -> None:
    """.env があれば読み込む（既存の環境変数は上書きしない）。

    python-dotenv への依存を避けるための最小実装。
    """
    path = path or (PROJECT_ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # 引用符つきの値は閉じ引用符までを値とする（値の中の # を壊さないため）。
        # 引用符が無い場合のみ、行末のコメント（' #' 以降）を落とす。
        if value[:1] in ('"', "'"):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            if " #" in value:
                value = value.split(" #", 1)[0]
            value = value.strip()

        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class MailSettings:
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    use_ssl: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender and self.recipients)


@dataclass
class Settings:
    timezone_name: str = "Asia/Tokyo"
    lookback_hours: int = 24
    max_articles: int = 140
    legal_min: int = 8
    notifiers: list[str] = field(default_factory=lambda: ["file"])
    anthropic_api_key: str = ""
    model: str = "claude-opus-5"
    sources_path: Path = DEFAULT_SOURCES
    archive_dir: Path = DEFAULT_ARCHIVE
    mail: MailSettings = field(default_factory=MailSettings)
    slack_webhook: str = ""
    discord_webhook: str = ""

    @property
    def tz(self):
        return load_tz(self.timezone_name)

    @property
    def use_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        mail = MailSettings(
            host=os.environ.get("SMTP_HOST", ""),
            port=_env_int("SMTP_PORT", 587),
            user=os.environ.get("SMTP_USER", ""),
            password=os.environ.get("SMTP_PASSWORD", ""),
            sender=os.environ.get("MAIL_FROM", "") or os.environ.get("SMTP_USER", ""),
            recipients=_env_list("MAIL_TO"),
            use_ssl=_env_bool("SMTP_USE_SSL", False),
        )
        return cls(
            timezone_name=os.environ.get("DIGEST_TIMEZONE", "Asia/Tokyo"),
            lookback_hours=_env_int("DIGEST_LOOKBACK_HOURS", 24),
            max_articles=_env_int("DIGEST_MAX_ARTICLES", 140),
            legal_min=_env_int("DIGEST_LEGAL_MIN", 8),
            notifiers=_env_list("DIGEST_NOTIFIERS", ["file"]),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=os.environ.get("DIGEST_MODEL", "claude-opus-5"),
            sources_path=Path(os.environ.get("DIGEST_SOURCES", str(DEFAULT_SOURCES))),
            archive_dir=Path(os.environ.get("DIGEST_ARCHIVE_DIR", str(DEFAULT_ARCHIVE))),
            mail=mail,
            slack_webhook=os.environ.get("SLACK_WEBHOOK_URL", ""),
            discord_webhook=os.environ.get("DISCORD_WEBHOOK_URL", ""),
        )


def load_sources_config(path: Path) -> dict[str, Any]:
    """sources.yaml を読み込む。"""
    if not path.exists():
        raise FileNotFoundError(f"ソース定義が見つかりません: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("defaults", {})
    data.setdefault("feeds", [])
    data.setdefault("google_news", {"enabled": False, "queries": []})
    return data
