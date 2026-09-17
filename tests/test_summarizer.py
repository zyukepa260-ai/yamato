import json
import sys
import types
from datetime import datetime, timezone

import pytest

from newsdigest.models import Article
from newsdigest.summarizer import (
    RESPONSE_SCHEMA,
    _digest_from_payload,
    build_article_block,
    summarize,
    summarize_fallback,
)

NOW = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def articles():
    return [
        Article(title="最高裁が違憲判断", url="https://a/1", source="裁判所",
                category="法学・司法", summary="判決概要", published=NOW, source_weight=2.6),
        Article(title="経済対策を決定", url="https://b/2", source="NHK",
                category="経済・ビジネス", summary="対策概要", published=NOW),
    ]


def test_schema_is_valid_json():
    json.dumps(RESPONSE_SCHEMA)
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert "legal_items" in RESPONSE_SCHEMA["required"]


def test_article_block_is_indexed(articles):
    block = build_article_block(articles)
    assert block.startswith("[0]")
    assert "[1]" in block
    # URLはモデルに渡さない（捏造を防ぐため番号で参照させる）
    assert "https://a/1" not in block


def test_invalid_source_indices_are_dropped(articles):
    payload = {
        "headline": "概況",
        "legal_items": [{"title": "T", "summary": "S", "significance": "I",
                         "tags": [], "sources": [0, 99, "x", -1, 0]}],
        "sections": [],
        "watchlist": [],
    }
    digest = _digest_from_payload(payload, articles, NOW)
    resolved = digest.legal_items[0].articles
    assert len(resolved) == 1
    assert resolved[0] is articles[0]


def test_empty_sections_are_dropped(articles):
    payload = {"headline": "", "legal_items": [], "watchlist": [],
               "sections": [{"category": "空", "items": []},
                            {"category": "経済", "items": [
                                {"title": "T", "summary": "S", "sources": [1]}]}]}
    digest = _digest_from_payload(payload, articles, NOW)
    assert [s.category for s in digest.sections] == ["経済"]


def test_fallback_separates_legal_from_others(articles):
    digest = summarize_fallback(articles, NOW, legal_min=1)
    assert digest.engine == "fallback"
    assert len(digest.legal_items) == 1
    assert digest.legal_items[0].title == "最高裁が違憲判断"
    assert [s.category for s in digest.sections] == ["経済・ビジネス"]


def test_summarize_without_api_key_uses_fallback(articles):
    assert summarize(articles, NOW, api_key="").engine == "fallback"


def test_summarize_with_no_articles():
    digest = summarize([], NOW, api_key="")
    assert digest.engine == "fallback"
    assert "ありません" in digest.headline


# ---------------------------------------------------------------------------
# Claude 呼び出しのモック
# ---------------------------------------------------------------------------
class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, payload, stop_reason="end_turn"):
        self.content = [_Block(json.dumps(payload, ensure_ascii=False))]
        self.stop_reason = stop_reason
        self.stop_details = None
        self.usage = types.SimpleNamespace(input_tokens=10, output_tokens=20)


class _Stream:
    def __init__(self, response, captured, kwargs):
        self._response = response
        captured.update(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


def install_fake_anthropic(monkeypatch, response, captured):
    module = types.ModuleType("anthropic")

    class FakeClient:
        def __init__(self, api_key=None, **kwargs):
            captured["api_key"] = api_key
            outer = self

            class Messages:
                def stream(self, **kwargs):
                    if isinstance(response, Exception):
                        raise response
                    return _Stream(response, captured, kwargs)

            self.messages = Messages()

    module.Anthropic = FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", module)


def test_claude_path_builds_digest_and_sends_expected_params(monkeypatch, articles):
    payload = {
        "headline": "概況テキスト",
        "legal_items": [{"title": "違憲判断", "summary": "要約", "significance": "影響",
                         "tags": ["憲法"], "sources": [0]}],
        "sections": [{"category": "経済・ビジネス",
                      "items": [{"title": "経済", "summary": "要約", "sources": [1]}]}],
        "watchlist": ["続報"],
    }
    captured: dict = {}
    install_fake_anthropic(monkeypatch, _Response(payload), captured)

    digest = summarize(articles, NOW, api_key="sk-test", legal_min=1)

    assert digest.engine == "claude"
    assert digest.headline == "概況テキスト"
    assert digest.legal_items[0].significance == "影響"
    assert digest.legal_items[0].articles[0] is articles[0]
    assert digest.watchlist == ["続報"]

    # リクエストの形を検証
    assert captured["api_key"] == "sk-test"
    assert captured["model"] == "claude-opus-5"
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["output_config"]["effort"] == "high"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["max_tokens"] == 64000


def test_api_failure_falls_back_without_raising(monkeypatch, articles):
    captured: dict = {}
    install_fake_anthropic(monkeypatch, RuntimeError("API障害"), captured)

    digest = summarize(articles, NOW, api_key="sk-test", legal_min=1)
    assert digest.engine == "fallback"
    assert "簡易版" in digest.headline


def test_refusal_falls_back(monkeypatch, articles):
    captured: dict = {}
    install_fake_anthropic(monkeypatch, _Response({}, stop_reason="refusal"), captured)

    digest = summarize(articles, NOW, api_key="sk-test", legal_min=1)
    assert digest.engine == "fallback"


def test_malformed_json_falls_back(monkeypatch, articles):
    captured: dict = {}

    class BadResponse(_Response):
        def __init__(self):
            self.content = [_Block("{ これはJSONではない")]
            self.stop_reason = "end_turn"
            self.stop_details = None
            self.usage = types.SimpleNamespace(input_tokens=1, output_tokens=1)

    install_fake_anthropic(monkeypatch, BadResponse(), captured)
    assert summarize(articles, NOW, api_key="sk-test").engine == "fallback"
