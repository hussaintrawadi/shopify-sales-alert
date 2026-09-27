"""Turns a day of orders into sales figures. Pure functions, no network."""

from dataclasses import dataclass, field

UNCATEGORIZED = "Uncategorized"
OTHER = "Other"
ALL_PRODUCTS = "All products"
# Differences smaller than this are per-unit rounding, not real adjustments.
ROUNDING_TOLERANCE = 1.0


@dataclass
class ProductRow:
    title: str
    category: str
    units: int = 0
    amount: float = 0.0


@dataclass
class CategoryRow:
    name: str
    units: int
    amount: float
    products: int


@dataclass
class SalesReport:
    currency: str
    orders: int = 0
    cancelled: int = 0
    test_skipped: int = 0
    units: int = 0
    gross: float = 0.0
    discounts: float = 0.0
    returns: float = 0.0
    net: float = 0.0
    shipping: float = 0.0
    taxes: float = 0.0
    taxes_included: bool = False
    other: float = 0.0
    total: float = 0.0
    products: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    by_category: dict = field(default_factory=dict)

    @property
    def aov(self):
        return self.total / self.orders if self.orders else 0.0


def amount(money_bag):
    try:
        return float(((money_bag or {}).get("shopMoney") or {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def categorize(line, group_by, rules=None):
    if group_by == "product_type":
        return ((line.get("product") or {}).get("productType") or "").strip() or UNCATEGORIZED
    if group_by == "vendor":
        return (line.get("vendor") or "").strip() or UNCATEGORIZED
    if group_by == "rules":
        title = (line.get("title") or "").lower()
        for category, keywords in rules or []:
            if any(k in title for k in keywords):
                return category
        return OTHER
    return ALL_PRODUCTS


def compute(orders, *, currency="USD", group_by="product_type", rules=None,
            include_test_orders=False):
    report = SalesReport(currency=currency)
    products = {}

    for order in orders:
        if order.get("test") and not include_test_orders:
            report.test_skipped += 1
            continue
        if order.get("cancelledAt"):
            report.cancelled += 1
            continue

        report.orders += 1
        report.currency = order.get("currencyCode") or report.currency
        taxes_included = bool(order.get("taxesIncluded"))
        report.taxes_included = report.taxes_included or taxes_included

        order_total = amount(order.get("currentTotalPriceSet"))
        tax = amount(order.get("currentTotalTaxSet"))
        shipping = amount(order.get("currentShippingPriceSet"))
        report.total += order_total
        report.taxes += tax
        report.shipping += shipping

        order_net = 0.0
        for line in order.get("lines") or []:
            ordered = int(line.get("quantity") or 0)
            if ordered <= 0:
                continue
            kept = max(int(line.get("currentQuantity") or 0), 0)
            unit = amount(line.get("originalUnitPriceSet"))
            unit_after_discounts = amount(line.get("discountedUnitPriceAfterAllDiscountsSet"))

            report.gross += unit * ordered
            report.discounts += max(unit - unit_after_discounts, 0.0) * ordered
            report.returns += unit_after_discounts * (ordered - kept)
            line_net = unit_after_discounts * kept
            order_net += line_net

            if kept == 0:
                continue
            report.units += kept
            product = line.get("product") or {}
            key = product.get("id") or line.get("title")
            row = products.get(key)
            if row is None:
                row = products[key] = ProductRow(
                    title=(line.get("title") or "Unknown product").strip(),
                    category=categorize(line, group_by, rules))
            row.units += kept
            row.amount += line_net

        # Whatever the lines, shipping and tax do not explain: tips, duties, fees, rounding.
        report.other += order_total - order_net - shipping - (0.0 if taxes_included else tax)

    report.net = report.gross - report.discounts - report.returns
    if abs(report.other) < ROUNDING_TOLERANCE:
        report.other = 0.0

    report.products = sorted(products.values(), key=lambda r: (r.amount, r.units), reverse=True)
    grouped = {}
    for row in report.products:
        grouped.setdefault(row.category, []).append(row)
    report.by_category = grouped
    report.categories = sorted(
        (CategoryRow(name=name, units=sum(r.units for r in rows),
                     amount=sum(r.amount for r in rows), products=len(rows))
         for name, rows in grouped.items()),
        key=lambda c: c.amount, reverse=True)
    return report
