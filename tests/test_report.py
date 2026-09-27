import pytest

from sales_alert.report import categorize, compute


def test_totals(orders):
    r = compute(orders)
    assert r.orders == 4
    assert r.cancelled == 1
    assert r.test_skipped == 1
    assert r.units == 8
    assert r.gross == pytest.approx(490)
    assert r.discounts == pytest.approx(14)
    assert r.returns == pytest.approx(25)
    assert r.net == pytest.approx(451)
    assert r.shipping == pytest.approx(10)
    assert r.taxes == pytest.approx(42.1)
    assert r.other == pytest.approx(3)  # the tip on order 1004
    assert r.total == pytest.approx(506.1)
    assert r.aov == pytest.approx(126.525)
    assert r.currency == "USD"


def test_breakdown_adds_up(orders):
    r = compute(orders)
    assert r.net + r.shipping + r.taxes + r.other == pytest.approx(r.total)


def test_products_ranked_by_sales(orders):
    r = compute(orders)
    assert [(p.title, p.units, round(p.amount, 2)) for p in r.products] == [
        ("Linen Shirt", 3, 174.0),
        ("Denim Jacket", 1, 120.0),
        ("Relaxed Chinos", 1, 72.0),
        ("Cotton Tee", 2, 50.0),
        ("Leather Belt", 1, 35.0),
    ]


def test_categories_by_product_type(orders):
    r = compute(orders)
    assert [(c.name, round(c.amount, 2), c.units, c.products) for c in r.categories][:2] == [
        ("Shirts", 174.0, 3, 1), ("Outerwear", 120.0, 1, 1)]


def test_group_by_vendor(orders):
    r = compute(orders, group_by="vendor")
    assert {c.name for c in r.categories} == {"Northwind", "Harbor"}


def test_group_by_rules(orders):
    rules = [("Tops", ["shirt", "tee"]), ("Bottoms", ["chino"])]
    r = compute(orders, group_by="rules", rules=rules)
    names = {c.name: c.products for c in r.categories}
    assert names == {"Tops": 2, "Bottoms": 1, "Other": 2}


def test_include_test_orders(orders):
    r = compute(orders, include_test_orders=True)
    assert r.orders == 5
    assert r.test_skipped == 0


def test_no_orders():
    r = compute([], currency="INR")
    assert r.orders == 0
    assert r.aov == 0
    assert r.currency == "INR"


def test_taxes_included_are_not_added_again():
    line = {"title": "Kurta", "quantity": 1, "currentQuantity": 1,
            "originalUnitPriceSet": {"shopMoney": {"amount": "1180.00"}},
            "discountedUnitPriceAfterAllDiscountsSet": {"shopMoney": {"amount": "1180.00"}},
            "product": {"id": "p1", "productType": "Kurtas"}}
    order = {"id": "o1", "currencyCode": "INR", "taxesIncluded": True,
             "currentTotalPriceSet": {"shopMoney": {"amount": "1180.00"}},
             "currentTotalTaxSet": {"shopMoney": {"amount": "180.00"}},
             "currentShippingPriceSet": {"shopMoney": {"amount": "0"}}, "lines": [line]}
    r = compute([order])
    assert r.taxes_included
    assert r.total == pytest.approx(1180)
    assert r.other == 0


def test_rounding_is_not_reported_as_other():
    line = {"title": "Tee", "quantity": 3, "currentQuantity": 3,
            "originalUnitPriceSet": {"shopMoney": {"amount": "10.00"}},
            "discountedUnitPriceAfterAllDiscountsSet": {"shopMoney": {"amount": "6.67"}},
            "product": {"id": "p1"}}
    order = {"id": "o1", "currentTotalPriceSet": {"shopMoney": {"amount": "20.00"}},
             "lines": [line]}
    assert compute([order]).other == 0


def test_deleted_product_is_uncategorized():
    assert categorize({"title": "Old thing", "product": None}, "product_type") == "Uncategorized"
