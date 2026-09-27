"""
Render a sample email from made-up orders, without touching Shopify:

    python scripts/demo.py

It writes email-preview.html, which you can open in a browser.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sales_alert.email_template import render_html  # noqa: E402
from sales_alert.report import compute  # noqa: E402


def main():
    orders = json.loads((ROOT / "tests" / "fixtures" / "orders.json").read_text())
    report = compute(orders)
    html = render_html(report, store_name="Demo Store", date_label="27 Sep 2026, Sunday",
                       brand_color="#1f2937", top_n=5)
    out = ROOT / "email-preview.html"
    out.write_text(f"<!doctype html><meta charset='utf-8'><body style='margin:24px;background:#fff'>{html}",
                   encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
