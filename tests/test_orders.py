from datetime import date
from zoneinfo import ZoneInfo

from sales_alert.orders import day_window, fetch_orders, orders_search


def test_day_window_in_store_timezone():
    start, end = day_window(ZoneInfo("Asia/Kolkata"), date(2026, 9, 27))
    assert orders_search(start, end) == (
        "created_at:>='2026-09-26T18:30:00Z' created_at:<'2026-09-27T18:30:00Z'")


def test_day_window_across_daylight_saving():
    # Clocks go back on 1 Nov 2026 in New York, so that day lasts 25 hours.
    start, end = day_window(ZoneInfo("America/New_York"), date(2026, 11, 1))
    assert orders_search(start, end) == (
        "created_at:>='2026-11-01T04:00:00Z' created_at:<'2026-11-02T05:00:00Z'")


class FakeShopify:
    def __init__(self):
        self.follow_ups = []

    def paginate(self, document, root, variables=None):
        assert root == "orders"
        assert variables["query"].startswith("created_at:>=")
        yield {"id": "o1", "lineItems": {"nodes": [{"id": "l1"}],
                                         "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}}
        yield {"id": "o2", "lineItems": {"nodes": [{"id": "l9"}],
                                         "pageInfo": {"hasNextPage": False, "endCursor": None}}}

    def query(self, document, variables):
        self.follow_ups.append(variables)
        if variables["cursor"] == "c1":
            return {"order": {"lineItems": {"nodes": [{"id": "l2"}],
                                            "pageInfo": {"hasNextPage": True, "endCursor": "c2"}}}}
        return {"order": {"lineItems": {"nodes": [{"id": "l3"}],
                                        "pageInfo": {"hasNextPage": False, "endCursor": None}}}}


def test_fetch_orders_collects_every_line_item():
    shopify = FakeShopify()
    start, end = day_window(ZoneInfo("UTC"), date(2026, 9, 27))
    orders = fetch_orders(shopify, start, end)
    assert [l["id"] for l in orders[0]["lines"]] == ["l1", "l2", "l3"]
    assert [l["id"] for l in orders[1]["lines"]] == ["l9"]
    assert shopify.follow_ups == [{"id": "o1", "cursor": "c1"}, {"id": "o1", "cursor": "c2"}]
    assert "lineItems" not in orders[0]
