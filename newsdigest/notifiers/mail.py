"""SMTP によるメール配信（HTML + プレーンテキストのマルチパート）。"""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

from ..config import MailSettings
from ..models import Digest
from ..render import render_html, render_text
from .base import DeliveryResult, Notifier

logger = logging.getLogger(__name__)


class MailNotifier(Notifier):
    name = "email"

    def __init__(self, settings: MailSettings):
        self.settings = settings

    def available(self) -> tuple[bool, str]:
        s = self.settings
        missing = []
        if not s.host:
            missing.append("SMTP_HOST")
        if not s.sender:
            missing.append("MAIL_FROM")
        if not s.recipients:
            missing.append("MAIL_TO")
        if missing:
            return False, f"未設定: {', '.join(missing)}"
        return True, ""

    def build_message(self, digest: Digest) -> MIMEMultipart:
        s = self.settings
        message = MIMEMultipart("alternative")
        subject = f"【{digest.date_label}】ニュースダイジェスト（法学重点）"
        message["Subject"] = Header(subject, "utf-8")
        message["From"] = formataddr((str(Header("ニュースダイジェスト", "utf-8")), s.sender))
        message["To"] = ", ".join(s.recipients)
        message["Date"] = formatdate(localtime=True)

        # マルチパートでは最後に添付したものが優先されるため text -> html の順に入れる
        message.attach(MIMEText(render_text(digest), "plain", "utf-8"))
        message.attach(MIMEText(render_html(digest), "html", "utf-8"))
        return message

    def send(self, digest: Digest) -> DeliveryResult:
        ok, reason = self.available()
        if not ok:
            return DeliveryResult(self.name, False, reason)

        s = self.settings
        message = self.build_message(digest)

        try:
            if s.use_ssl or s.port == 465:
                server = smtplib.SMTP_SSL(s.host, s.port, timeout=30)
            else:
                server = smtplib.SMTP(s.host, s.port, timeout=30)
            with server:
                server.ehlo()
                if not (s.use_ssl or s.port == 465):
                    try:
                        server.starttls()
                        server.ehlo()
                    except smtplib.SMTPNotSupportedError:
                        logger.warning("STARTTLS 非対応のサーバーです。平文で送信します。")
                if s.user and s.password:
                    server.login(s.user, s.password)
                server.sendmail(s.sender, s.recipients, message.as_string())
        except smtplib.SMTPAuthenticationError as exc:
            return DeliveryResult(
                self.name,
                False,
                f"認証失敗: {exc}. Gmail の場合はアプリパスワードを使用してください",
            )
        except Exception as exc:
            return DeliveryResult(self.name, False, f"{type(exc).__name__}: {exc}")

        return DeliveryResult(self.name, True, f"{len(s.recipients)}件の宛先に送信")
