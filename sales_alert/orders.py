"""Fetches the orders placed in one day, with every line item."""

from datetime import datetime, time, timedelta, timezone

LINE_FIELDS = """
fragment SaleLine on LineItem {
  id
  title
  vendor
  quantity
  currentQuantity
  originalUnitPriceSet { shopMoney { amount } }
  discountedUnitPriceAfterAllDiscountsSet { shopMoney { amount } }
  product { id productType }
}
"""

# Pages are kept small so each request stays well under Shopify's query cost limit.
# Orders with more than 10 line items get the rest in a follow-up query.
ORDERS_QUERY = """
query SalesOrders($cursor: String, $query: String) {
  orders(first: 10, after: $cursor, query: $query, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      name
      createdAt
      cancelledAt
      test
      currencyCode
      taxesIncluded
      currentTotalPriceSet { shopMoney { amount } }
      currentTotalTaxSet { shopMoney { amount } }
      currentShippingPriceSet { shopMoney { amount } }
      lineItems(first: 10) {
        pageInfo { hasNextPage endCursor }
        nodes { ...SaleLine }
      }
    }
  }
}
""" + LINE_FIELDS

ORDER_LINES_QUERY = """
query OrderLineItems($id: ID!, $cursor: String) {
  order(id: $id) {
    lineItems(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { ...SaleLine }
    }
  }
}
""" + LINE_FIELDS


def day_window(zone, day):
    """Start and end of a calendar day in the store's timezone (handles DST days)."""
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start, end


def orders_search(start, end):
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    start_utc = start.astimezone(timezone.utc).strftime(fmt)
    end_utc = end.astimezone(timezone.utc).strftime(fmt)
    return f"created_at:>='{start_utc}' created_at:<'{end_utc}'"


def fetch_orders(shopify, start, end):
    """Every order created in [start, end), each with its complete list of line items."""
    orders = []
    for order in shopify.paginate(ORDERS_QUERY, "orders", {"query": orders_search(start, end)}):
        connection = order.pop("lineItems")
        lines = list(connection["nodes"])
        page = connection["pageInfo"]
        while page["hasNextPage"]:
            more = shopify.query(ORDER_LINES_QUERY, {"id": order["id"], "cursor": page["endCursor"]})
            connection = more["order"]["lineItems"]
            lines.extend(connection["nodes"])
            page = connection["pageInfo"]
        order["lines"] = lines
        orders.append(order)
    return orders
