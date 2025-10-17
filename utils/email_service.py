"""
Email sending service (scaffold)

Default provider: Naver SMTP. Allows override via config dict.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import smtplib
from email.message import EmailMessage
import ssl


@dataclass
class EmailConfig:
    host: str = "smtp.naver.com"
    port: int = 587
    user: Optional[str] = None
    password: Optional[str] = None
    from_name: Optional[str] = None


def send_email_with_attachments(config: EmailConfig, to_addrs: List[str], subject: str, body_html: str, attachments: List[tuple[str, bytes, str]] = []) -> bool:
    """
    attachments: list of tuples (filename, file_bytes, mime_type)
    returns True on success
    """
    msg = EmailMessage()
    from_addr = config.user or ""
    msg["From"] = f"{config.from_name or ''} <{from_addr}>" if config.from_name else from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.add_alternative(body_html, subtype='html')

    for fname, fbytes, mime_type in attachments:
        maintype, _, subtype = (mime_type.partition('/') if '/' in mime_type else ("application","/","octet-stream"))
        msg.add_attachment(fbytes, maintype=maintype, subtype=subtype, filename=fname)

    context = ssl.create_default_context()
    with smtplib.SMTP(config.host, config.port) as server:
        server.starttls(context=context)
        if config.user and config.password:
            server.login(config.user, config.password)
        server.send_message(msg)
    return True

