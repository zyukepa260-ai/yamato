"""ローカルファイルへの書き出し。

3種類を出力する:
  dashboard-YYYYMMDD.html  絞り込み・グラフ付きのダッシュボード（ブラウザ用）
  digest-YYYYMMDD.html     メール配信と同じ静的HTML
  digest-YYYYMMDD.md       Markdown（他ツールへの取り込み用）
さらに、最新のダッシュボードを index.html にも複製する。
"""

from __future__ import annotations

from pathlib import Path

from ..dashboard import render_dashboard
from ..models import Digest
from ..render import render_html, render_markdown
from .base import DeliveryResult, Notifier


class FileNotifier(Notifier):
    name = "file"

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def available(self) -> tuple[bool, str]:
        return True, ""

    def send(self, digest: Digest) -> DeliveryResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = digest.generated_at.strftime("%Y%m%d")

        dashboard = render_dashboard(digest)
        dashboard_path = self.output_dir / f"dashboard-{stamp}.html"
        dashboard_path.write_text(dashboard, encoding="utf-8")

        # 常に最新版を開けるようにしておく
        (self.output_dir / "index.html").write_text(dashboard, encoding="utf-8")

        (self.output_dir / f"digest-{stamp}.html").write_text(
            render_html(digest), encoding="utf-8"
        )
        (self.output_dir / f"digest-{stamp}.md").write_text(
            render_markdown(digest), encoding="utf-8"
        )

        return DeliveryResult(
            self.name, True, f"{dashboard_path}（最新版: {self.output_dir / 'index.html'}）"
        )
