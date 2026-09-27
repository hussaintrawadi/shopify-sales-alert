"""Entry point: python -m sales_alert"""

import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .config import ROOT, ConfigError, load_dotenv, load_settings
from .email_template import render_html, render_text, subject_line
from .mailer import MailError, send
from .orders import day_window, fetch_orders
from .report import compute
from .shopify import Shopify, ShopifyError, resolve_access_token

USER_AGENT = f"shopify-sales-alert/{__version__}"


def store_zone(tz_name):
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"Unknown timezone '{tz_name}', using UTC.")
        return timezone.utc


def run():
    settings = load_settings()

    token = resolve_access_token(
        settings.store_domain, access_token=settings.access_token,
        client_id=settings.client_id, client_secret=settings.client_secret,
        user_agent=USER_AGENT)
    shopify = Shopify(settings.store_domain, token, settings.api_version, user_agent=USER_AGENT)

    shop = shopify.shop()
    store_name = settings.store_name or shop["name"]
    zone = store_zone(settings.timezone or shop.get("ianaTimezone") or "UTC")
    day = settings.report_date or (datetime.now(zone).date() - timedelta(days=1))
    start, end = day_window(zone, day)
    date_label = day.strftime("%d %b %Y, %A")

    print(f"{store_name}: orders placed {start.isoformat()} to {end.isoformat()}")
    orders = fetch_orders(shopify, start, end)
    print(f"Fetched {len(orders)} orders.")

    report = compute(orders, currency=shop.get("currencyCode") or "USD",
                     group_by=settings.group_by, rules=settings.category_rules,
                     include_test_orders=settings.include_test_orders)
    subject = subject_line(store_name, date_label, report)
    html = render_html(report, store_name=store_name, date_label=date_label,
                       brand_color=settings.brand_color, top_n=settings.top_n,
                       show_categories=settings.group_by != "none")
    text = render_text(report, store_name=store_name, date_label=date_label, top_n=settings.top_n)
    print(f"Subject: {subject}")

    if settings.dry_run:
        settings.preview_path.write_text(html, encoding="utf-8")
        print(f"DRY_RUN is on, so nothing was sent. Preview: {settings.preview_path}")
        return
    if not report.orders and not settings.send_when_no_orders:
        print("No orders and SEND_WHEN_NO_ORDERS is false, so no email today.")
        return

    send(settings.email_provider, sender=settings.email_from, recipients=settings.email_to,
         subject=subject, html=html, text=text, api_key=settings.email_api_key,
         smtp=settings.smtp)
    print(f"Sent to {', '.join(settings.email_to)}")


def main():
    load_dotenv(ROOT / ".env")
    try:
        run()
    except (ConfigError, ShopifyError, MailError) as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
