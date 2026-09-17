"""生成したダイジェストをローカルに保存する。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Digest


def save(digest: Digest, archive_dir: Path) -> Path:
    """ダイジェストをJSONとして保存し、そのパスを返す。

    後から「あの日何を配信したか」を再確認したり、
    要約の品質を見直したりするために残す。
    """
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"digest-{digest.generated_at.strftime('%Y%m%d')}.json"
    path.write_text(
        json.dumps(digest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
