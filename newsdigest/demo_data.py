"""ネットワークなしで描画・配信を確認するためのサンプルデータ。"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import Article, Digest, DigestItem, DigestSection


def build_demo_digest(now: datetime) -> Digest:
    """レイアウト確認用のダミーダイジェスト。内容はすべて架空。"""
    recent = now - timedelta(hours=5)

    def art(title: str, source: str, url: str, category: str) -> Article:
        return Article(
            title=title, url=url, source=source, category=category,
            summary="（サンプルデータ）", published=recent,
        )

    digest = Digest(generated_at=now, engine="claude")
    digest.headline = (
        "（これはレイアウト確認用のサンプルです）最高裁が個人情報の第三者提供をめぐり"
        "初の判断を示したほか、改正労働基準法の施行日が確定した。"
    )
    digest.legal_items = [
        DigestItem(
            title="最高裁、個人情報の第三者提供めぐり初判断",
            summary=(
                "最高裁第三小法廷は、利用者の同意なく第三者へ提供された行動履歴について、"
                "提供元企業の説明義務違反を認める判断を示した。二審判決を破棄し、"
                "損害額の算定のため審理を高裁へ差し戻した。"
            ),
            significance=(
                "同意取得フローを「形式的な同意」に依存している事業者は、"
                "説明内容の具体性を見直す必要がある。特に広告配信目的でのデータ連携は"
                "プライバシーポリシーの記載粒度が争点になり得る。"
            ),
            tags=["個人情報", "最高裁", "プライバシー"],
            articles=[
                art("最高裁、個人情報の第三者提供めぐり初判断", "裁判所 新着判例",
                    "https://example.com/hanrei/1", "法学・司法"),
                art("個人情報提供で企業の説明義務認める", "Google:最高裁判決",
                    "https://example.com/news/1", "法学・司法"),
            ],
        ),
        DigestItem(
            title="改正労働基準法、来年4月1日施行が決定",
            summary=(
                "厚生労働省は改正労働基準法の施行期日を定める政令を公布した。"
                "割増賃金率の引き上げと勤務間インターバルの努力義務化が同時に施行される。"
            ),
            significance=(
                "就業規則の改定と勤怠システムの設定変更が必要になる。"
                "特に裁量労働制を採用している事業場では、対象業務の再確認が求められる。"
            ),
            tags=["労働法", "法改正"],
            articles=[
                art("改正労働基準法の施行期日を定める政令", "e-Gov パブリックコメント",
                    "https://example.com/egov/1", "法学・司法"),
            ],
        ),
    ]
    digest.sections = [
        DigestSection(
            category="経済・ビジネス",
            items=[
                DigestItem(
                    title="日銀が政策金利を据え置き",
                    summary="金融政策決定会合で現行の誘導目標を維持することを決めた。",
                    articles=[art("日銀が政策金利を据え置き", "NHK 経済",
                                  "https://example.com/econ/1", "経済・ビジネス")],
                )
            ],
        ),
        DigestSection(
            category="テクノロジー",
            items=[
                DigestItem(
                    title="国内主要クラウド、生成AI向け基盤を拡張",
                    summary="大規模モデルの推論需要に対応するため設備投資を増やすと発表した。",
                    articles=[art("クラウド各社が生成AI基盤を拡張", "ITmedia NEWS",
                                  "https://example.com/tech/1", "テクノロジー")],
                )
            ],
        ),
    ]
    digest.watchlist = [
        "差し戻し審での損害額算定の基準",
        "改正労基法に伴う就業規則モデルの公表時期",
        "個人情報保護委員会によるガイドライン改訂の有無",
    ]
    digest.total_collected = 312
    digest.total_after_dedupe = 187
    return digest
