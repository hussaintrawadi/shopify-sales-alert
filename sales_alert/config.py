"""Settings come from environment variables: GitHub secrets and variables, or a local .env file."""

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .mailer import PROVIDERS, parse_recipients

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_VERSION = "2026-07"
DEFAULT_BRAND_COLOR = "#1f2937"
GROUP_BY_CHOICES = ("product_type", "vendor", "rules", "none")


class ConfigError(ValueError):
    """Raised when a setting is missing or invalid."""


@dataclass
class Settings:
    store_domain: str
    access_token: str | None
    client_id: str | None
    client_secret: str | None
    api_version: str
    email_provider: str
    email_api_key: str | None
    email_from: str | None
    email_to: list
    smtp: dict | None
    timezone: str | None
    store_name: str | None
    brand_color: str
    dry_run: bool
    preview_path: Path
    group_by: str
    category_rules: list | None
    top_n: int
    report_date: date | None
    include_test_orders: bool
    send_when_no_orders: bool


def _get(environ, name, default=None):
    # GitHub passes unset secrets and variables as empty strings, so treat "" as unset.
    value = environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _bool(environ, name, default):
    value = _get(environ, name)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{name} must be true or false, not '{value}'.")


def _int(environ, name, default, minimum=0):
    value = _get(environ, name)
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, not '{value}'.") from None
    if number < minimum:
        raise ConfigError(f"{name} must be {minimum} or more.")
    return number


def load_dotenv(path):
    """Load KEY=value lines from a .env file. Real environment variables win."""
    path = Path(path)
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if value[:1] in ("'", '"') and value[0] in value[1:]:
            value = value[1:value.index(value[0], 1)]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)


def normalize_store_domain(value):
    """Accept "my-store", "my-store.myshopify.com" or a full admin URL."""
    domain = re.sub(r"^https?://", "", value.strip().lower()).split("/")[0]
    if "." not in domain:
        domain += ".myshopify.com"
    return domain


def load_settings(environ=None):
    environ = os.environ if environ is None else environ
    missing = []

    def required(name):
        value = _get(environ, name)
        if value is None:
            missing.append(name)
        return value

    store = required("SHOPIFY_STORE_DOMAIN")
    access_token = _get(environ, "SHOPIFY_ACCESS_TOKEN")
    client_id = _get(environ, "SHOPIFY_CLIENT_ID")
    client_secret = _get(environ, "SHOPIFY_CLIENT_SECRET")
    if not access_token and not (client_id and client_secret):
        missing.append("SHOPIFY_ACCESS_TOKEN (or SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET)")

    dry_run = _bool(environ, "DRY_RUN", False)
    provider = _get(environ, "EMAIL_PROVIDER", "resend").lower()
    if provider not in PROVIDERS:
        raise ConfigError(f"EMAIL_PROVIDER must be one of {', '.join(PROVIDERS)}, not '{provider}'.")

    email_from = api_key = smtp = None
    email_to = []
    if not dry_run:
        email_from = required("EMAIL_FROM")
        email_to = parse_recipients(required("EMAIL_TO"))
        if provider == "smtp":
            smtp = {
                "host": required("SMTP_HOST"),
                "port": _int(environ, "SMTP_PORT", 587, minimum=1),
                "username": required("SMTP_USERNAME"),
                "password": required("SMTP_PASSWORD"),
            }
        else:
            api_key = required("EMAIL_API_KEY")

    if missing:
        raise ConfigError("Missing required settings: " + ", ".join(missing))

    brand_color = _get(environ, "BRAND_COLOR", DEFAULT_BRAND_COLOR)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", brand_color):
        raise ConfigError(f"BRAND_COLOR must look like #1f2937, not '{brand_color}'.")

    group_by = _get(environ, "GROUP_BY", "product_type").lower()
    if group_by not in GROUP_BY_CHOICES:
        raise ConfigError(f"GROUP_BY must be one of {', '.join(GROUP_BY_CHOICES)}, not '{group_by}'.")
    rules = None
    if group_by == "rules":
        rules = load_category_rules(ROOT / _get(environ, "CATEGORY_RULES_FILE", "categories.yaml"))

    report_date = _get(environ, "REPORT_DATE")
    if report_date:
        try:
            report_date = date.fromisoformat(report_date)
        except ValueError:
            raise ConfigError(f"REPORT_DATE must look like 2026-09-27, not '{report_date}'.") from None

    return Settings(
        store_domain=normalize_store_domain(store),
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        api_version=_get(environ, "SHOPIFY_API_VERSION", DEFAULT_API_VERSION),
        email_provider=provider,
        email_api_key=api_key,
        email_from=email_from,
        email_to=email_to,
        smtp=smtp,
        timezone=_get(environ, "REPORT_TIMEZONE"),
        store_name=_get(environ, "STORE_NAME"),
        brand_color=brand_color,
        dry_run=dry_run,
        preview_path=ROOT / _get(environ, "PREVIEW_FILE", "email-preview.html"),
        group_by=group_by,
        category_rules=rules,
        top_n=_int(environ, "TOP_N", 10, minimum=1),
        report_date=report_date or None,
        include_test_orders=_bool(environ, "INCLUDE_TEST_ORDERS", False),
        send_when_no_orders=_bool(environ, "SEND_WHEN_NO_ORDERS", True),
    )


def load_category_rules(path):
    """Return [(category, [keywords])] in file order. The first matching category wins."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"GROUP_BY is 'rules' but {path.name} does not exist. "
                          "Copy categories.example.yaml to get started.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} should map category names to lists of keywords.")
    rules = []
    for category, keywords in data.items():
        if not isinstance(keywords, list):
            raise ConfigError(f"'{category}' in {path.name} should be a list of keywords.")
        rules.append((str(category), [str(k).strip().lower() for k in keywords if str(k).strip()]))
    return rules
