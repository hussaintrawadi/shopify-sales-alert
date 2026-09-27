import os
from datetime import date

import pytest

from sales_alert import config
from sales_alert.config import ConfigError, load_dotenv, load_settings

BASE = {
    "SHOPIFY_STORE_DOMAIN": "demo-store",
    "SHOPIFY_CLIENT_ID": "id",
    "SHOPIFY_CLIENT_SECRET": "secret",
    "EMAIL_PROVIDER": "brevo",
    "EMAIL_API_KEY": "xkeysib-test",
    "EMAIL_FROM": "Sales <sales@example.com>",
    "EMAIL_TO": "a@example.com",
}


def test_defaults():
    s = load_settings(BASE)
    assert s.store_domain == "demo-store.myshopify.com"
    assert s.group_by == "product_type"
    assert s.top_n == 10
    assert s.report_date is None
    assert s.include_test_orders is False
    assert s.send_when_no_orders is True


def test_report_date():
    assert load_settings({**BASE, "REPORT_DATE": "2026-09-01"}).report_date == date(2026, 9, 1)
    with pytest.raises(ConfigError):
        load_settings({**BASE, "REPORT_DATE": "yesterday"})


def test_missing_settings_are_listed():
    with pytest.raises(ConfigError) as err:
        load_settings({"EMAIL_PROVIDER": "brevo"})
    assert "SHOPIFY_STORE_DOMAIN" in str(err.value)
    assert "EMAIL_API_KEY" in str(err.value)


def test_rules_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    with pytest.raises(ConfigError, match="categories.example.yaml"):
        load_settings({**BASE, "GROUP_BY": "rules"})
    (tmp_path / "categories.yaml").write_text("Seeds:\n  - Seed\n  - bulb\nTools:\n  - trowel\n")
    s = load_settings({**BASE, "GROUP_BY": "rules"})
    assert s.category_rules == [("Seeds", ["seed", "bulb"]), ("Tools", ["trowel"])]


@pytest.mark.parametrize("name,value", [("GROUP_BY", "colour"), ("TOP_N", "0"),
                                        ("BRAND_COLOR", "#12345")])
def test_rejects_bad_values(name, value):
    with pytest.raises(ConfigError):
        load_settings({**BASE, name: value})


def test_load_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "EMAIL_FROM=Stock Alerts <alerts@example.com>\n"
        'EMAIL_TO="a@example.com, b@example.com"  # two people\n'
        "export DRY_RUN=true   # preview only\n"
        "SHOPIFY_STORE_DOMAIN=from-file\n")
    environ = {"SHOPIFY_STORE_DOMAIN": "from-env"}
    monkeypatch.setattr(os, "environ", environ)
    load_dotenv(env)
    assert environ == {
        "EMAIL_FROM": "Stock Alerts <alerts@example.com>",
        "EMAIL_TO": "a@example.com, b@example.com",
        "DRY_RUN": "true",
        "SHOPIFY_STORE_DOMAIN": "from-env",
    }
