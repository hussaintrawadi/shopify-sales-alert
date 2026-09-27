from sales_alert.email_template import money, render_html, render_text, subject_line
from sales_alert.report import compute


def test_money():
    assert money(1234.5, "USD") == "$1,234.50"
    assert money(1234.5, "INR", 0) == "₹1,234"
    assert money(10, "XYZ") == "10.00 XYZ"
    assert money(-3, "USD") == "-$3.00"


def test_subject(orders):
    r = compute(orders)
    assert subject_line("Demo", "27 Sep 2026, Sunday", r) == (
        "Demo sales for 27 Sep 2026, Sunday: $506 from 4 orders")
    assert subject_line("Demo", "d", compute([])).endswith("no orders")


def test_html_sections(orders):
    html = render_html(compute(orders), store_name="Demo <Shop>", date_label="d",
                       brand_color="#123456")
    assert "Demo &lt;Shop&gt; &middot; Daily sales report" in html
    for heading in ("Sales breakdown", "Sales by category", "Top sellers by category",
                    "Top 10 products", "Other (tips, duties, fees)"):
        assert heading in html
    assert "1 cancelled order(s)" in html
    assert "1 test order(s)" in html


def test_html_without_categories(orders):
    html = render_html(compute(orders), store_name="Demo", date_label="d",
                       brand_color="#123456", show_categories=False)
    assert "Sales by category" not in html


def test_top_n_limits_rows(orders):
    html = render_html(compute(orders), store_name="Demo", date_label="d",
                       brand_color="#123456", top_n=2)
    assert "Top 2 products" in html


def test_no_orders_message():
    html = render_html(compute([]), store_name="Demo", date_label="27 Sep", brand_color="#123456")
    assert "No orders were placed on 27 Sep." in html


def test_text_version(orders):
    text = render_text(compute(orders), store_name="Demo", date_label="d")
    assert "Total sales: $506.10" in text
    assert "1. Linen Shirt: 3 units, $174.00" in text
