from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from ..models.smtp_config import SmtpConfig
from ..services.smtp_service import decrypt_password


async def send_email(
    smtp_config: SmtpConfig,
    to_addrs: list[str],
    subject: str,
    body_html: str | None = None,
    body_text: str | None = None,
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    reply_to: str | None = None,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = (
        f"{smtp_config.from_name} <{smtp_config.from_email}>"
        if smtp_config.from_name
        else smtp_config.from_email
    )
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject

    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    if reply_to:
        msg["Reply-To"] = reply_to

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    all_recipients = list(to_addrs)
    if cc_addrs:
        all_recipients.extend(cc_addrs)
    if bcc_addrs:
        all_recipients.extend(bcc_addrs)

    password = decrypt_password(smtp_config.password)

    # use_ssl=True → 隐式 SSL（端口 465）
    # use_tls=True → STARTTLS（端口 587）
    # 两者均 False → 明文
    await aiosmtplib.send(
        msg,
        hostname=smtp_config.host,
        port=smtp_config.port,
        username=smtp_config.username,
        password=password,
        use_tls=smtp_config.use_ssl,
        start_tls=smtp_config.use_tls and not smtp_config.use_ssl,
        recipients=all_recipients,
    )
