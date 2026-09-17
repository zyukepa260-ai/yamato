import urllib.parse
from pathlib import Path

from newsdigest.config import DEFAULT_SOURCES, MailSettings, Settings, load_sources_config
from newsdigest.sources import build_feed_specs, build_google_news_url


def test_google_news_url_encodes_query_and_locale():
    url = build_google_news_url("最高裁 判決", recency="when:2d")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "news.google.com"
    assert params["q"] == ["最高裁 判決 when:2d"]
    assert params["hl"] == ["ja"]
    assert params["ceid"] == ["JP:ja"]


def test_google_news_url_without_recency():
    params = urllib.parse.parse_qs(urllib.parse.urlparse(
        build_google_news_url("test", recency="")).query)
    assert params["q"] == ["test"]


def test_disabled_entries_are_excluded():
    config = {
        "defaults": {},
        "feeds": [
            {"name": "有効", "url": "https://a/1", "category": "社会"},
            {"name": "無効", "url": "https://a/2", "category": "社会", "enabled": False},
            {"name": "URLなし", "category": "社会"},
        ],
        "google_news": {"enabled": True, "queries": [
            {"q": "テスト", "name": "T", "category": "法学・司法"},
            {"q": "無効", "enabled": False},
        ]},
    }
    specs = build_feed_specs(config)
    assert [s.name for s in specs] == ["有効", "Google:T"]


def test_google_news_can_be_turned_off():
    config = {"feeds": [], "google_news": {"enabled": False, "queries": [{"q": "x"}]}}
    assert build_feed_specs(config) == []


def test_shipped_config_is_loadable_and_law_weighted():
    """同梱の sources.yaml が壊れていないこと、法学分野が重点化されていること。"""
    specs = build_feed_specs(load_sources_config(DEFAULT_SOURCES))
    assert len(specs) > 20

    legal = [s for s in specs if s.category == "法学・司法"]
    others = [s for s in specs if s.category != "法学・司法"]
    assert len(legal) >= 20
    # 法学分野の平均重みが他分野より明確に高いこと
    avg_legal = sum(s.weight for s in legal) / len(legal)
    avg_other = sum(s.weight for s in others) / len(others)
    assert avg_legal > avg_other * 1.5


def test_settings_defaults_without_env(monkeypatch):
    for key in ["DIGEST_TIMEZONE", "DIGEST_LOOKBACK_HOURS", "DIGEST_NOTIFIERS",
                "ANTHROPIC_API_KEY", "SMTP_HOST", "MAIL_TO"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("newsdigest.config.load_dotenv", lambda *a, **k: None)

    settings = Settings.from_env()
    assert settings.timezone_name == "Asia/Tokyo"
    assert settings.lookback_hours == 24
    assert settings.notifiers == ["file"]
    assert settings.use_llm is False


def test_settings_reads_env(monkeypatch):
    monkeypatch.setattr("newsdigest.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("DIGEST_NOTIFIERS", "email, slack")
    monkeypatch.setenv("DIGEST_LOOKBACK_HOURS", "12")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setenv("MAIL_TO", "a@example.com, b@example.com")

    settings = Settings.from_env()
    assert settings.notifiers == ["email", "slack"]
    assert settings.lookback_hours == 12
    assert settings.use_llm is True
    assert settings.mail.recipients == ["a@example.com", "b@example.com"]


def test_invalid_int_env_falls_back_to_default(monkeypatch):
    monkeypatch.setattr("newsdigest.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("DIGEST_LOOKBACK_HOURS", "not-a-number")
    assert Settings.from_env().lookback_hours == 24


def test_dotenv_does_not_override_existing_env(monkeypatch, tmp_path):
    from newsdigest.config import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text('FOO=from_file\nBAR="quoted value"  # コメント\n', encoding="utf-8")
    monkeypatch.setenv("FOO", "from_environment")
    monkeypatch.delenv("BAR", raising=False)

    load_dotenv(env_file)
    import os
    assert os.environ["FOO"] == "from_environment"
    assert os.environ["BAR"] == "quoted value"


def test_mail_settings_configured_flag():
    assert not MailSettings().configured
    assert MailSettings(host="h", sender="s", recipients=["r"]).configured
