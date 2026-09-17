"""Claude による要約生成。APIキーが無い場合は非LLMのフォールバックに切り替える。

設計上のポイント:
- 記事URLはモデルに生成させず、こちらが渡した「記事番号」で参照させる。
  これによりリンクの捏造が原理的に起こらない。
- 法学分野は独立したセクションとして、実務上の意味まで書かせる。
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime

from .models import Article, Digest, DigestItem, DigestSection
from .ranker import LEGAL_CATEGORY

logger = logging.getLogger(__name__)

MAX_TOKENS = 64000

SYSTEM_PROMPT = """\
あなたは日本語のニュースダイジェストを編集する専門家です。読者は法律実務に関心の高い
ビジネスパーソンで、毎朝これ1通で「昨日何が起きたか」を把握したいと考えています。

編集方針:
1. **法学・司法分野を最重点**とする。判決・法改正・立法動向・規制動向は、
   事実関係だけでなく「誰にどう影響するのか」という実務上の意味まで踏み込んで書く。
2. 法学以外の分野（政治・経済・国際・テクノロジー・科学医療・社会・文化）も
   偏りなくカバーし、その日の重要な動きを漏らさない。
3. 事実に忠実であること。与えられた記事に書かれていない事実、数値、固有名詞を
   決して追加しない。記事の情報だけでは断定できないことは断定しない。
4. 複数の記事が同じ出来事を報じている場合は1つのトピックにまとめ、
   その記事番号をすべて sources に列挙する。
5. 文章は簡潔な「である調」で書く。前置きや挨拶は書かない。

注意: 記事のURLは出力しない。必ず与えられた「記事番号」で参照すること。\
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "その日全体を1〜2文で表す要約。",
        },
        "legal_items": {
            "type": "array",
            "description": "法学・司法分野の重点トピック。最重要のものから並べる。",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "トピックの見出し"},
                    "summary": {
                        "type": "string",
                        "description": "何が起きたかの要約。3〜5文程度。",
                    },
                    "significance": {
                        "type": "string",
                        "description": "実務上の意味・影響範囲・今後の注目点。2〜3文程度。",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "分野タグ（例: 知的財産, 労働法, 個人情報）",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "根拠とした記事番号",
                    },
                },
                "required": ["title", "summary", "significance", "tags", "sources"],
                "additionalProperties": False,
            },
        },
        "sections": {
            "type": "array",
            "description": "法学以外の分野別まとめ。",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {
                                    "type": "string",
                                    "description": "1〜3文の要約",
                                },
                                "sources": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                            },
                            "required": ["title", "summary", "sources"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["category", "items"],
                "additionalProperties": False,
            },
        },
        "watchlist": {
            "type": "array",
            "items": {"type": "string"},
            "description": "今日以降に続報を追うべき論点。3〜5項目。",
        },
    },
    "required": ["headline", "legal_items", "sections", "watchlist"],
    "additionalProperties": False,
}


def build_article_block(articles: list[Article]) -> str:
    """モデルに渡す記事一覧テキストを作る。番号が sources の参照キーになる。"""
    lines = []
    for index, article in enumerate(articles):
        published = (
            article.published.astimezone().strftime("%m/%d %H:%M")
            if article.published
            else "日時不明"
        )
        coverage = f" / {article.duplicate_count}媒体" if article.duplicate_count > 1 else ""
        lines.append(
            f"[{index}] ({article.category}) {article.title}\n"
            f"    出典: {article.source} / {published}{coverage}\n"
            f"    概要: {article.summary or '（本文要約なし）'}"
        )
    return "\n".join(lines)


def build_user_prompt(articles: list[Article], date_label: str, legal_min: int) -> str:
    legal_count = sum(1 for a in articles if a.category == LEGAL_CATEGORY or a.legal_score > 0)
    return f"""\
以下は{date_label}朝時点で収集した最新ニュース{len(articles)}件です
（うち法学関連と判定されたもの: 約{legal_count}件）。

これをもとに、今朝配信するニュースダイジェストを作成してください。

要件:
- legal_items: 法学・司法分野の重点トピックを**{legal_min}件以上**（重要なものが多ければ最大15件まで）。
  各トピックには必ず significance（実務上の意味）を書くこと。
- sections: 法学以外を分野ごとにまとめる。1分野あたり2〜5トピック。
  該当する記事が無い分野は省略してよい。
- sources には、そのトピックの根拠とした記事番号を必ず1つ以上入れること。
- watchlist: 続報を追うべき論点を3〜5件。

=== 記事一覧 ===
{build_article_block(articles)}
"""


def _resolve_sources(indices: list, articles: list[Article]) -> list[Article]:
    """モデルが返した記事番号を Article に解決する（範囲外は無視）。"""
    resolved: list[Article] = []
    seen: set[int] = set()
    for raw in indices or []:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(articles) and index not in seen:
            seen.add(index)
            resolved.append(articles[index])
    return resolved


def _digest_from_payload(
    payload: dict, articles: list[Article], generated_at: datetime
) -> Digest:
    digest = Digest(generated_at=generated_at, engine="claude")
    digest.headline = str(payload.get("headline", "")).strip()

    for raw in payload.get("legal_items") or []:
        digest.legal_items.append(
            DigestItem(
                title=str(raw.get("title", "")).strip(),
                summary=str(raw.get("summary", "")).strip(),
                significance=str(raw.get("significance", "")).strip(),
                tags=[str(t) for t in (raw.get("tags") or [])],
                articles=_resolve_sources(raw.get("sources"), articles),
            )
        )

    for raw_section in payload.get("sections") or []:
        section = DigestSection(category=str(raw_section.get("category", "その他")).strip())
        for raw_item in raw_section.get("items") or []:
            section.items.append(
                DigestItem(
                    title=str(raw_item.get("title", "")).strip(),
                    summary=str(raw_item.get("summary", "")).strip(),
                    articles=_resolve_sources(raw_item.get("sources"), articles),
                )
            )
        if section.items:
            digest.sections.append(section)

    digest.watchlist = [str(w).strip() for w in (payload.get("watchlist") or []) if str(w).strip()]
    return digest


def summarize_with_claude(
    articles: list[Article],
    generated_at: datetime,
    api_key: str,
    model: str = "claude-opus-5",
    legal_min: int = 8,
    date_label: str = "",
) -> Digest:
    """Claude に要約させて Digest を組み立てる。"""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_user_prompt(articles, date_label or generated_at.strftime("%Y年%m月%d日"), legal_min)

    # 出力が長くなるためストリーミングを使う（HTTPタイムアウト回避）
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"モデルが生成を拒否しました: {getattr(detail, 'explanation', '')}")

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise RuntimeError("モデル応答にテキストが含まれていませんでした")

    payload = json.loads(text)
    digest = _digest_from_payload(payload, articles, generated_at)

    usage = response.usage
    logger.info(
        "Claude 要約完了: 入力%dトークン / 出力%dトークン",
        getattr(usage, "input_tokens", 0),
        getattr(usage, "output_tokens", 0),
    )
    return digest


def summarize_fallback(
    articles: list[Article], generated_at: datetime, legal_min: int = 8
) -> Digest:
    """LLMを使わない簡易ダイジェスト。

    APIキーが無い場合やAPI障害時でも「配信が止まらない」ことを優先する。
    記事の見出しと配信元の要約をそのまま使う（新しい文章は生成しない）。
    """
    digest = Digest(generated_at=generated_at, engine="fallback")

    legal = [a for a in articles if a.category == LEGAL_CATEGORY or a.legal_score >= 2.0]
    legal.sort(key=lambda a: a.score, reverse=True)
    legal_ids = {id(a) for a in legal}
    others = [a for a in articles if id(a) not in legal_ids]

    digest.headline = (
        f"本日の収集件数は{len(articles)}件。"
        f"うち法学関連は{len(legal)}件。（自動要約は未使用）"
    )

    for article in legal[: max(legal_min, 10)]:
        digest.legal_items.append(
            DigestItem(
                title=article.title,
                summary=article.summary or "（配信元に要約なし。リンク先を参照）",
                significance="",
                tags=article.matched_terms[:4],
                articles=[article],
            )
        )

    grouped: dict[str, list[Article]] = defaultdict(list)
    for article in others:
        grouped[article.category].append(article)

    for category, items in grouped.items():
        items.sort(key=lambda a: a.score, reverse=True)
        section = DigestSection(category=category)
        for article in items[:5]:
            section.items.append(
                DigestItem(
                    title=article.title,
                    summary=article.summary or "",
                    articles=[article],
                )
            )
        if section.items:
            digest.sections.append(section)

    digest.watchlist = []
    return digest


def summarize(
    articles: list[Article],
    generated_at: datetime,
    api_key: str = "",
    model: str = "claude-opus-5",
    legal_min: int = 8,
    date_label: str = "",
) -> Digest:
    """要約を生成する。Claude が使えない・失敗した場合は簡易版に自動で切り替える。"""
    if not articles:
        return Digest(generated_at=generated_at, engine="fallback", headline="対象記事がありませんでした。")

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY が未設定のため簡易要約で生成します")
        return summarize_fallback(articles, generated_at, legal_min)

    try:
        return summarize_with_claude(
            articles, generated_at, api_key, model, legal_min, date_label
        )
    except Exception as exc:
        # 配信を止めないことを最優先し、簡易要約にフォールバックする
        logger.error("Claude 要約に失敗したため簡易要約に切り替えます: %r", exc)
        digest = summarize_fallback(articles, generated_at, legal_min)
        digest.headline = f"[自動要約に失敗したため簡易版で配信] {digest.headline}"
        return digest
