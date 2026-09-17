"""ローカルファイルへの書き出し（動作確認・アーカイブ用）。"""

from __future__ import annotations

from pathlib import Path

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
        html_path = self.output_dir / f"digest-{stamp}.html"
        md_path = self.output_dir / f"digest-{stamp}.md"
        html_path.write_text(render_html(digest), encoding="utf-8")
        md_path.write_text(render_markdown(digest), encoding="utf-8")
        return DeliveryResult(self.name, True, f"{html_path} / {md_path}")
