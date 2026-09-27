"""Sends the report through Resend, Brevo or any SMTP server."""

import json
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import requests

PROVIDERS = ("resend", "brevo", "smtp")


class MailError(RuntimeError):
    """Raised when the email provider refuses the message."""


def parse_recipients(raw):
    """Accept "a@x.com, b@y.com", "a@x.com; b@y.com" or a JSON list."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [str(x).strip() for x in json.loads(raw) if str(x).strip()]
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]


def split_sender(sender, default_name):
    """Turn "Name <email>" or "email" into (name, email)."""
    name, address = parseaddr(sender)
    return (name or default_name), (address or sender.strip())


def send(provider, *, sender, recipients, subject, html, text, api_key=None, smtp=None,
         session=None):
    if provider == "resend":
        _send_resend(api_key, sender, recipients, subject, html, text, session or requests)
    elif provider == "brevo":
        _send_brevo(api_key, sender, recipients, subject, html, text, session or requests)
    elif provider == "smtp":
        _send_smtp(smtp, sender, recipients, subject, html, text)
    else:
        raise MailError(f"Unknown EMAIL_PROVIDER '{provider}'. Use one of: {', '.join(PROVIDERS)}.")


def _send_resend(api_key, sender, recipients, subject, html, text, http):
    resp = http.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": sender, "to": recipients, "subject": subject, "html": html, "text": text},
        timeout=30,
    )
    if not 200 <= resp.status_code < 300:
        raise MailError(f"Resend refused the email: HTTP {resp.status_code} {resp.text[:400]}")


def _send_brevo(api_key, sender, recipients, subject, html, text, http):
    name, address = split_sender(sender, "Shopify reports")
    resp = http.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "sender": {"name": name, "email": address},
            "to": [{"email": r} for r in recipients],
            "subject": subject,
            "htmlContent": html,
            "textContent": text,
        },
        timeout=30,
    )
    if not 200 <= resp.status_code < 300:
        raise MailError(f"Brevo refused the email: HTTP {resp.status_code} {resp.text[:400]}")


def _send_smtp(smtp, sender, recipients, subject, html, text):
    name, address = split_sender(sender, "")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((name, address)) if name else address
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    try:
        if smtp["port"] == 465:
            server = smtplib.SMTP_SSL(smtp["host"], smtp["port"], context=context, timeout=30)
        else:
            server = smtplib.SMTP(smtp["host"], smtp["port"], timeout=30)
            server.starttls(context=context)
        with server:
            server.login(smtp["username"], smtp["password"])
            server.send_message(msg, from_addr=address, to_addrs=recipients)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"SMTP send failed: {exc}") from exc
