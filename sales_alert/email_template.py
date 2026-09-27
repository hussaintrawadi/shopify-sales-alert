"""Renders the sales report as an email: inline-styled HTML plus a plain-text fallback."""

from html import escape

REPO_URL = "https://github.com/hussaintrawadi/shopify-sales-alert"
CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$", "CAD": "C$",
                    "JPY": "¥", "NZD": "NZ$", "SGD": "S$"}
NEGATIVE = "#b42318"
BORDER = "#e5e7eb"
SOFT = "#f6f7f9"
TEXT = "#1f2937"
MUTED = "#6b7280"


def money(value, currency, decimals=2):
    symbol = CURRENCY_SYMBOLS.get((currency or "").upper())
    number = f"{abs(value):,.{decimals}f}"
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{number}" if symbol else f"{sign}{number} {currency}".strip()


def subject_line(store_name, date_label, report):
    if not report.orders:
        return f"{store_name} sales for {date_label}: no orders"
    noun = "order" if report.orders == 1 else "orders"
    return (f"{store_name} sales for {date_label}: "
            f"{money(report.total, report.currency, 0)} from {report.orders} {noun}")


def _kpi(label, value, color):
    return (f'<td style="padding:5px;" width="50%" valign="top">'
            f'<div style="background:{SOFT};border:1px solid {BORDER};border-radius:10px;'
            f'padding:14px 10px;text-align:center;">'
            f'<div style="font-size:11px;letter-spacing:.4px;text-transform:uppercase;'
            f'color:{color};font-weight:700;">{label}</div>'
            f'<div style="font-size:22px;font-weight:700;color:{TEXT};margin-top:6px;">{value}</div>'
            f'</div></td>')


def _section(title, color):
    return (f'<h3 style="color:{color};margin:26px 0 8px;font-size:16px;'
            f'border-bottom:2px solid {BORDER};padding-bottom:6px;">{escape(title)}</h3>')


def _units(n):
    return f"{n:,} unit" if n == 1 else f"{n:,} units"


def _table(head, rows, widths=None):
    cols = ""
    if widths:
        cols = "<colgroup>" + "".join(f'<col style="width:{w};">' for w in widths) + "</colgroup>"
    layout = "table-layout:fixed;" if widths else ""
    return (f'<table role="presentation" style="width:100%;border-collapse:collapse;{layout}'
            f'border:1px solid {BORDER};font-size:13px;">{cols}{head}{"".join(rows)}</table>')


def _th(label, align="left", width=""):
    w = f"width:{width};" if width else ""
    return (f'<th style="padding:9px 12px;text-align:{align};font-size:11px;'
            f'text-transform:uppercase;{w}">{label}</th>')


def _td(content, align="left", bold=False, color=TEXT, nowrap=False):
    weight = "font-weight:700;" if bold else ""
    wrap = "white-space:nowrap;" if nowrap else "word-break:break-word;"
    return (f'<td style="padding:9px 12px;border-bottom:1px solid #eee;text-align:{align};'
            f'color:{color};{weight}{wrap}">{content}</td>')


def _product_table(rows, currency, color, numbered=False):
    head = (f'<tr style="background:{color};color:#ffffff;">'
            + (_th("#", width="28px") if numbered else "")
            + _th("Product") + _th("Units", "right") + _th("Sales", "right") + "</tr>")
    body = []
    for i, r in enumerate(rows, 1):
        bg = "#ffffff" if i % 2 else SOFT
        body.append(f'<tr style="background:{bg};">'
                    + (_td(str(i), color=MUTED) if numbered else "")
                    + _td(escape(r.title)) + _td(f"{r.units:,}", "right", bold=True)
                    + _td(money(r.amount, currency), "right", nowrap=True) + "</tr>")
    widths = ["36px", "auto", "70px", "110px"] if numbered else ["auto", "70px", "110px"]
    return _table(head, body, widths)


def _breakdown(report):
    cur = report.currency
    rows = [("Gross sales", money(report.gross, cur), False, False)]
    if report.discounts:
        rows.append(("Discounts", "- " + money(report.discounts, cur), False, True))
    if report.returns:
        rows.append(("Returns and removals", "- " + money(report.returns, cur), False, True))
    rows.append(("Net sales", money(report.net, cur), True, False))
    if report.shipping:
        rows.append(("Shipping", "+ " + money(report.shipping, cur), False, False))
    if report.taxes:
        if report.taxes_included:
            rows.append(("Taxes (already in prices)", money(report.taxes, cur), False, False))
        else:
            rows.append(("Taxes", "+ " + money(report.taxes, cur), False, False))
    if report.other:
        label = "Other (tips, duties, fees)"
        value = ("+ " if report.other > 0 else "- ") + money(abs(report.other), cur)
        rows.append((label, value, False, report.other < 0))
    rows.append(("Total sales", money(report.total, cur), True, False))
    return rows


def render_html(report, *, store_name, date_label, brand_color, top_n=10, show_categories=True):
    cur = report.currency
    e = escape

    if not report.orders:
        body = (f'<div style="padding:22px;font-size:15px;color:{MUTED};">'
                f'No orders were placed on {e(date_label)}.</div>')
    else:
        kpis = ('<table role="presentation" style="width:100%;border-collapse:collapse;'
                'table-layout:fixed;"><tr>'
                + _kpi("Total sales", money(report.total, cur, 0), brand_color)
                + _kpi("Orders", f"{report.orders:,}", brand_color)
                + "</tr><tr>"
                + _kpi("Units sold", f"{report.units:,}", brand_color)
                + _kpi("Average order", money(report.aov, cur, 0), brand_color)
                + "</tr></table>")

        breakdown_rows = []
        for label, value, bold, negative in _breakdown(report):
            highlight = f"background:{SOFT};" if label == "Total sales" else ""
            breakdown_rows.append(
                f'<tr style="{highlight}">'
                + _td(e(label), color="#374151")
                + _td(value, "right", bold=bold, color=NEGATIVE if negative else TEXT, nowrap=True)
                + "</tr>")
        parts = [
            kpis,
            f'<div style="padding:8px 8px 0;font-size:13px;color:{MUTED};">'
            f'{len(report.products):,} products sold across {report.orders:,} orders.</div>',
            f'<div style="padding:0 8px;">{_section("Sales breakdown", brand_color)}'
            f'{_table("", breakdown_rows)}</div>',
        ]

        if show_categories and report.categories:
            head = (f'<tr style="background:{brand_color};color:#ffffff;">' + _th("Category")
                    + _th("Sales", "right") + _th("Units", "right") + _th("Products", "right") + "</tr>")
            rows = []
            for i, c in enumerate(report.categories, 1):
                bg = "#ffffff" if i % 2 else SOFT
                rows.append(f'<tr style="background:{bg};">' + _td(e(c.name), bold=True)
                            + _td(money(c.amount, cur), "right", bold=True, nowrap=True)
                            + _td(f"{c.units:,}", "right") + _td(f"{c.products:,}", "right") + "</tr>")
            parts.append(f'<div style="padding:0 8px;">{_section("Sales by category", brand_color)}'
                         f'{_table(head, rows, ["auto", "110px", "70px", "95px"])}</div>')

            blocks = []
            for c in report.categories:
                rows = report.by_category.get(c.name, [])
                block = (f'<div style="margin:16px 0 6px;font-size:14px;font-weight:700;color:{TEXT};">'
                         f'{e(c.name)} <span style="color:{MUTED};font-weight:400;">'
                         f'{money(c.amount, cur)}, {_units(c.units)}</span></div>'
                         + _product_table(rows[:top_n], cur, brand_color))
                if len(rows) > top_n:
                    rest = rows[top_n:]
                    block += (f'<div style="padding:6px 12px;font-size:12px;color:{MUTED};">'
                              f'and {len(rest)} more ({_units(sum(r.units for r in rest))}, '
                              f'{money(sum(r.amount for r in rest), cur)})</div>')
                blocks.append(block)
            parts.append(f'<div style="padding:0 8px;">'
                         f'{_section("Top sellers by category", brand_color)}{"".join(blocks)}</div>')

        parts.append(f'<div style="padding:0 8px;">{_section(f"Top {top_n} products", brand_color)}'
                     f'{_product_table(report.products[:top_n], cur, brand_color, numbered=True)}</div>')

        notes = []
        if report.cancelled:
            notes.append(f"{report.cancelled} cancelled order(s) are left out of every figure.")
        if report.test_skipped:
            notes.append(f"{report.test_skipped} test order(s) are left out of every figure.")
        if notes:
            parts.append(f'<div style="margin:16px 8px 0;padding:10px 16px;background:{SOFT};'
                         f'border:1px solid {BORDER};border-radius:6px;font-size:13px;color:#4b5563;">'
                         + " ".join(notes) + "</div>")
        body = "".join(parts)

    return f"""<div style="font-family:-apple-system,'Segoe UI',Arial,Helvetica,sans-serif;max-width:700px;margin:0 auto;color:{TEXT};">
  <div style="background:{brand_color};color:#ffffff;padding:22px 24px;border-radius:12px 12px 0 0;">
    <div style="font-size:21px;font-weight:700;">{e(store_name)} &middot; Daily sales report</div>
    <div style="opacity:.85;font-size:14px;margin-top:4px;">{e(date_label)}</div>
  </div>
  <div style="background:#ffffff;border:1px solid {BORDER};border-top:none;padding:18px 14px 8px;border-radius:0 0 12px 12px;">
    {body}
    <div style="margin:24px 8px 4px;padding:10px 16px;background:{SOFT};border-radius:6px;font-size:11px;color:{MUTED};">
      Orders placed on {e(date_label)} &middot; Sent by <a href="{REPO_URL}" style="color:{MUTED};">Shopify Sales Alert</a>
    </div>
  </div>
</div>"""


def render_text(report, *, store_name, date_label, top_n=10):
    cur = report.currency
    lines = [f"{store_name} daily sales report", date_label, ""]
    if not report.orders:
        lines += [f"No orders were placed on {date_label}.", ""]
    else:
        lines += [
            f"Total sales: {money(report.total, cur)}",
            f"Orders: {report.orders:,}",
            f"Units sold: {report.units:,}",
            f"Average order: {money(report.aov, cur)}",
            "",
        ]
        lines += [f"{label}: {value}" for label, value, _, _ in _breakdown(report)]
        lines += ["", f"TOP {top_n} PRODUCTS"]
        for i, r in enumerate(report.products[:top_n], 1):
            lines.append(f"{i}. {r.title}: {_units(r.units)}, {money(r.amount, cur)}")
        lines.append("")
        if report.cancelled:
            lines.append(f"{report.cancelled} cancelled order(s) are left out of every figure.")
        if report.test_skipped:
            lines.append(f"{report.test_skipped} test order(s) are left out of every figure.")
    lines.append(f"Sent by Shopify Sales Alert ({REPO_URL})")
    return "\n".join(lines)
