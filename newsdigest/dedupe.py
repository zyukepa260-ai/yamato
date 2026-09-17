"""重複記事の除去。

同じニュースが複数媒体から流れてくるため、
1) URL の正規化による完全重複の除去
2) 見出しの類似度による準重複の除去
の2段階で圧縮する。日本語は分かち書きが無いため、文字バイグラムで類似度を測る。
"""

from __future__ import annotations

import re
import urllib.parse
from collections import defaultdict

from .models import Article

# 計測用パラメータを剥がすためのクエリキー
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "cmpid", "spm", "oc")
_NOISE_RE = re.compile(r"[\s　、。，．,.\-―–—…「」『』（）()\[\]【】“”\"'!！?？:：;；/|]+")

# 準重複と判定する閾値。
# Jaccard だけでは長さの違う言い換え（「…判断」/「…判断を示す」）を取り逃がし、
# 重なり率だけでは「東京地裁/大阪地裁」のような別ニュースを誤結合するため、
# 両方を満たす場合のみ重複とみなす。
OVERLAP_THRESHOLD = 0.80
JACCARD_THRESHOLD = 0.45
MIN_BIGRAMS = 5      # これ未満の短い見出しは完全一致のみ重複扱い


def normalize_url(url: str) -> str:
    """トラッキングパラメータとフラグメントを除いたURLを返す。"""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), netloc, path, urllib.parse.urlencode(query), "")
    )


def normalize_title(title: str) -> str:
    """記号・空白を除去した比較用の見出し。"""
    return _NOISE_RE.sub("", title).lower()


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    if not intersection:
        return 0.0
    return intersection / len(a | b)


def _overlap(a: set[str], b: set[str]) -> float:
    """重なり率（intersection / 小さい方のサイズ）。言い換えや加筆に強い。"""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def is_similar(
    a: set[str],
    b: set[str],
    overlap_threshold: float = OVERLAP_THRESHOLD,
    jaccard_threshold: float = JACCARD_THRESHOLD,
) -> bool:
    """2つの見出し（バイグラム集合）が同じニュースを指すかを判定する。"""
    if not a or not b:
        return False
    if min(len(a), len(b)) < MIN_BIGRAMS:
        return a == b
    return _overlap(a, b) >= overlap_threshold and _jaccard(a, b) >= jaccard_threshold


def _prefer(current: Article, candidate: Article) -> Article:
    """重複した2件のうち残す方を選ぶ。

    一次情報（source_weight が高い）を優先し、次に本文要約が充実している方。
    """
    if candidate.source_weight != current.source_weight:
        return candidate if candidate.source_weight > current.source_weight else current
    if len(candidate.summary) > len(current.summary) + 40:
        return candidate
    return current


def deduplicate(
    articles: list[Article],
    overlap_threshold: float = OVERLAP_THRESHOLD,
    jaccard_threshold: float = JACCARD_THRESHOLD,
) -> list[Article]:
    """重複を除いた記事リストを返す。

    残った記事の `duplicate_count` に、まとめられた件数が入る。
    """
    # --- 第1段階: URL の完全一致 ---
    by_url: dict[str, Article] = {}
    for article in articles:
        key = normalize_url(article.url)
        existing = by_url.get(key)
        if existing is None:
            by_url[key] = article
        else:
            winner = _prefer(existing, article)
            winner.duplicate_count = existing.duplicate_count + article.duplicate_count
            by_url[key] = winner

    candidates = list(by_url.values())

    # --- 第2段階: 見出しの類似度 ---
    kept: list[Article] = []
    kept_bigrams: list[set[str]] = []
    index: dict[str, list[int]] = defaultdict(list)   # バイグラム -> kept のインデックス

    for article in candidates:
        norm = normalize_title(article.title)
        grams = _bigrams(norm)
        if not grams:
            kept.append(article)
            kept_bigrams.append(grams)
            continue

        # 共通バイグラムを持つものだけを比較対象にする（全件比較を避ける）
        seen: set[int] = set()
        for gram in grams:
            seen.update(index.get(gram, ()))

        duplicate_of = -1
        for position in seen:
            if is_similar(grams, kept_bigrams[position], overlap_threshold, jaccard_threshold):
                duplicate_of = position
                break

        if duplicate_of >= 0:
            existing = kept[duplicate_of]
            merged_count = existing.duplicate_count + article.duplicate_count
            winner = _prefer(existing, article)
            winner.duplicate_count = merged_count
            kept[duplicate_of] = winner
            # 勝者が入れ替わった場合はバイグラムも更新
            if winner is not existing:
                kept_bigrams[duplicate_of] = _bigrams(normalize_title(winner.title))
            continue

        position = len(kept)
        kept.append(article)
        kept_bigrams.append(grams)
        for gram in grams:
            index[gram].append(position)

    return kept
