"""収集から配信までを、ネットワークを使わずに通しで確認する。"""

from datetime import datetime, timezone

from newsdigest.config import MailSettings, Settings
from newsdigest.models import Article
from newsdigest.pipeline import build_digest, run

NOW = datetime(2026, 9, 16, 23, 0, tzinfo=timezone.utc)


def fake_articles():
    return [
        Article(title="最高裁が違憲判断、法改正へ", url="https://a/1", source="裁判所 新着判例",
                category="法学・司法", summary="判決の概要", published=NOW, source_weight=2.6),
        Article(title="最高裁が違憲判断、法改正へと報じられる", url="https://b/2", source="Google:最高裁判決",
                category="法学・司法", summary="同じ話題", published=NOW, source_weight=2.4),
        Article(title="改正個人情報保護法が施行", url="https://c/3", source="個人情報保護委員会",
                category="法学・司法", summary="施行の概要", published=NOW, source_weight=2.1),
        Article(title="日銀が政策金利を据え置き", url="https://d/4", source="NHK 経済",
                category="経済・ビジネス", summary="金融政策", published=NOW),
        Article(title="新型ロケット打ち上げ成功", url="https://e/5", source="NHK 科学",
                category="科学・医療", summary="打ち上げ", published=NOW),
    ]


def make_settings(tmp_path, notifiers):
    return Settings(
        notifiers=notifiers,
        anthropic_api_key="",           # 簡易要約を使う
        archive_dir=tmp_path / "archive",
        legal_min=2,
        mail=MailSettings(),
    )


def patch_collect(monkeypatch, failed=None):
    monkeypatch.setattr(
        "newsdigest.pipeline.collect",
        lambda specs, lookback_hours=24, now=None: (fake_articles(), failed or []),
    )


def test_build_digest_end_to_end(monkeypatch, tmp_path):
    patch_collect(monkeypatch, failed=["壊れたフィード (HTTP 404)"])
    digest = build_digest(make_settings(tmp_path, ["file"]), now=NOW)

    assert digest.total_collected == 5
    # 重複した最高裁の記事がまとまっている
    assert digest.total_after_dedupe == 4
    assert digest.failed_sources == ["壊れたフィード (HTTP 404)"]
    # 法学が重点セクションに入り、その他は分野別に分かれる
    assert len(digest.legal_items) >= 2
    categories = {s.category for s in digest.sections}
    assert "経済・ビジネス" in categories
    assert "科学・医療" in categories


def test_run_writes_archive_and_delivers(monkeypatch, tmp_path):
    patch_collect(monkeypatch)
    settings = make_settings(tmp_path, ["file"])
    report = run(settings, now=NOW)

    assert report.delivered
    assert report.archive_path.endswith(".json")

    archive_dir = tmp_path / "archive"
    written = sorted(p.name for p in archive_dir.iterdir())
    assert any(name.endswith(".html") for name in written)
    assert any(name.endswith(".md") for name in written)
    assert any(name.endswith(".json") for name in written)

    html = (archive_dir / "digest-20260917.html").read_text(encoding="utf-8")
    assert "法学・司法［重点］" in html
    # 日付は JST に変換されている（23:00 UTC = 翌日 08:00 JST）
    assert "2026年09月17日" in html


def test_run_reports_failure_when_channel_unconfigured(monkeypatch, tmp_path):
    patch_collect(monkeypatch)
    settings = make_settings(tmp_path, ["email"])   # SMTP未設定
    report = run(settings, now=NOW)

    assert not report.delivered
    assert report.deliveries[0].channel == "email"
    assert "未設定" in report.deliveries[0].detail


def test_no_deliver_skips_channels(monkeypatch, tmp_path):
    patch_collect(monkeypatch)
    report = run(make_settings(tmp_path, ["file"]), now=NOW, deliver=False)
    assert report.deliveries == []
    assert report.archive_path      # アーカイブは残る
