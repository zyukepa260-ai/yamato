"""コマンドラインインターフェース。

    python -m newsdigest run        # 収集して配信（毎朝8時に実行されるのはこれ）
    python -m newsdigest preview    # 配信せずに内容だけ確認
    python -m newsdigest doctor     # フィードの疎通確認と設定チェック
    python -m newsdigest demo       # サンプル内容で配信テスト（ネット不要）
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import logging
import sys
import time
from datetime import datetime, timezone

from .collector import fetch_feed
from .config import Settings, load_sources_config
from .demo_data import build_demo_digest
from .notifiers import build_notifiers
from .pipeline import build_digest, run
from .render import render_markdown
from .sources import build_feed_specs


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
def cmd_run(settings: Settings, args) -> int:
    report = run(settings, deliver=not args.no_deliver)

    print(f"\n生成完了: {report.digest.date_label}")
    print(f"  収集 {report.digest.total_collected}件 → 重複除去後 {report.digest.total_after_dedupe}件")
    print(f"  法学トピック {len(report.digest.legal_items)}件 / その他 {len(report.digest.sections)}分野")
    print(f"  要約エンジン: {report.digest.engine}")
    if report.archive_path:
        print(f"  保存先: {report.archive_path}")

    if report.digest.failed_sources:
        print(f"\n取得できなかったフィード ({len(report.digest.failed_sources)}件):")
        for name in report.digest.failed_sources[:10]:
            print(f"  - {name}")
        print("  ※ `python -m newsdigest doctor` で詳細を確認できます")

    if args.no_deliver:
        return 0

    print("\n配信結果:")
    for result in report.deliveries:
        mark = "成功" if result.ok else "失敗"
        print(f"  [{mark}] {result.channel}: {result.detail}")

    if not report.deliveries:
        print("  配信チャネルが設定されていません（DIGEST_NOTIFIERS を確認してください）")
        return 1
    return 0 if report.delivered else 1


def cmd_preview(settings: Settings, args) -> int:
    digest = build_digest(settings)
    print(render_markdown(digest))
    return 0


def cmd_demo(settings: Settings, args) -> int:
    digest = build_demo_digest(datetime.now(settings.tz))
    if args.no_deliver:
        print(render_markdown(digest))
        return 0

    notifiers = build_notifiers(settings)
    if not notifiers:
        print("配信チャネルが設定されていません（DIGEST_NOTIFIERS を確認してください）")
        return 1

    print("サンプル内容で配信テストを行います。\n")
    ok = False
    for notifier in notifiers:
        result = notifier.send(digest)
        mark = "成功" if result.ok else "失敗"
        print(f"  [{mark}] {result.channel}: {result.detail}")
        ok = ok or result.ok
    return 0 if ok else 1


def cmd_doctor(settings: Settings, args) -> int:
    print("=" * 68)
    print(" 設定チェック")
    print("=" * 68)
    print(f"  タイムゾーン      : {settings.timezone_name}")
    print(f"  収集対象期間      : 直近 {settings.lookback_hours} 時間")
    print(f"  LLM要約           : {'有効（' + settings.model + '）' if settings.use_llm else '無効（ANTHROPIC_API_KEY 未設定 → 簡易要約）'}")
    print(f"  配信チャネル      : {', '.join(settings.notifiers) or '(なし)'}")
    for notifier in build_notifiers(settings):
        ok, reason = notifier.available()
        print(f"    - {notifier.name:8} : {'設定OK' if ok else reason}")

    config = load_sources_config(settings.sources_path)
    specs = build_feed_specs(config)

    print()
    print("=" * 68)
    print(f" フィード疎通確認（{len(specs)}件）")
    print("=" * 68)

    def probe(spec):
        started = time.monotonic()
        result = fetch_feed(spec)
        return spec, result, time.monotonic() - started

    alive = 0
    dead: list[str] = []
    legal_alive = 0

    with futures.ThreadPoolExecutor(max_workers=12) as pool:
        for spec, result, elapsed in pool.map(probe, specs):
            if result.ok:
                alive += 1
                if spec.category == "法学・司法":
                    legal_alive += 1
                print(f"  [OK] {spec.name:28} {len(result.articles):3}件  {elapsed:4.1f}s")
            else:
                dead.append(spec.name)
                print(f"  [NG] {spec.name:28} {result.error}")

    print()
    print(f"  生存: {alive}/{len(specs)}  （うち法学分野: {legal_alive}件）")
    if dead:
        print(f"  応答なし: {len(dead)}件 → config/sources.yaml で enabled: false にするか URL を修正してください")
    if legal_alive == 0:
        print("  警告: 法学分野のフィードが1つも取得できていません。重点分野が空になります。")
        return 1
    return 0 if alive else 1


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsdigest",
        description="毎朝8時に届く、法学重点の全分野ニュースダイジェスト",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細ログを出力")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="収集・要約して配信する（定時実行はこれ）")
    p_run.add_argument("--no-deliver", action="store_true", help="配信せず生成のみ行う")
    p_run.set_defaults(func=cmd_run)

    p_preview = sub.add_parser("preview", help="配信せずMarkdownで内容を確認する")
    p_preview.set_defaults(func=cmd_preview)

    p_demo = sub.add_parser("demo", help="サンプル内容で配信テスト（ネットワーク不要）")
    p_demo.add_argument("--no-deliver", action="store_true", help="配信せず表示のみ")
    p_demo.set_defaults(func=cmd_demo)

    p_doctor = sub.add_parser("doctor", help="設定とフィードの疎通を確認する")
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    settings = Settings.from_env()
    return args.func(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
