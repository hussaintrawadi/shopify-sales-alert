import sales_alert.__main__ as app


class FakeShopify:
    def __init__(self, orders):
        self.orders = orders

    def shop(self):
        return {"name": "Demo Store", "currencyCode": "USD", "ianaTimezone": "America/New_York"}


def test_dry_run_writes_preview(tmp_path, monkeypatch, orders, capsys):
    preview = tmp_path / "preview.html"
    captured = {}

    def fake_fetch(shopify, start, end):
        captured["window"] = (start.isoformat(), end.isoformat())
        return orders

    monkeypatch.setattr(app, "Shopify", lambda *a, **k: FakeShopify(orders))
    monkeypatch.setattr(app, "fetch_orders", fake_fetch)
    for name, value in {"SHOPIFY_STORE_DOMAIN": "demo", "SHOPIFY_ACCESS_TOKEN": "t",
                        "DRY_RUN": "true", "PREVIEW_FILE": str(preview),
                        "REPORT_DATE": "2026-09-27"}.items():
        monkeypatch.setenv(name, value)
    app.run()
    assert captured["window"] == ("2026-09-27T00:00:00-04:00", "2026-09-28T00:00:00-04:00")
    assert "Linen Shirt" in preview.read_text()
    assert "$506 from 4 orders" in capsys.readouterr().out


def test_no_orders_can_skip_email(monkeypatch):
    sent = []
    monkeypatch.setattr(app, "Shopify", lambda *a, **k: FakeShopify([]))
    monkeypatch.setattr(app, "fetch_orders", lambda *a: [])
    monkeypatch.setattr(app, "send", lambda *a, **k: sent.append(k))
    for name, value in {"SHOPIFY_STORE_DOMAIN": "demo", "SHOPIFY_ACCESS_TOKEN": "t",
                        "EMAIL_API_KEY": "k", "EMAIL_FROM": "a@x.com", "EMAIL_TO": "b@x.com",
                        "SEND_WHEN_NO_ORDERS": "false"}.items():
        monkeypatch.setenv(name, value)
    app.run()
    assert sent == []
