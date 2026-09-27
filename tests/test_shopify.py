import pytest

from conftest import FakeResponse
from sales_alert.shopify import Shopify, ShopifyError, resolve_access_token


def page(nodes, has_next, cursor=None):
    return FakeResponse(200, {"data": {"things": {
        "nodes": nodes, "pageInfo": {"hasNextPage": has_next, "endCursor": cursor}}}})


def test_paginate_follows_cursors(fake_session):
    session = fake_session([page([1, 2], True, "c1"), page([3], False)])
    client = Shopify("demo.myshopify.com", "t", "2026-07", session=session, sleep=lambda s: None)
    assert list(client.paginate("query", "things")) == [1, 2, 3]
    assert session.calls[0][1]["json"]["variables"]["cursor"] is None
    assert session.calls[1][1]["json"]["variables"]["cursor"] == "c1"
    assert session.calls[0][0] == "https://demo.myshopify.com/admin/api/2026-07/graphql.json"


def test_retries_when_throttled(fake_session):
    throttled = FakeResponse(200, {"errors": [{"message": "Throttled",
                                               "extensions": {"code": "THROTTLED"}}]})
    session = fake_session([throttled, FakeResponse(429, {}), page([1], False)])
    waits = []
    client = Shopify("demo.myshopify.com", "t", "2026-07", session=session, sleep=waits.append)
    assert list(client.paginate("query", "things")) == [1]
    assert waits == [2, 4]


def test_graphql_errors_raise(fake_session):
    session = fake_session([FakeResponse(200, {"errors": [{"message": "Field 'x' doesn't exist"}]})])
    client = Shopify("demo.myshopify.com", "t", "2026-07", session=session, sleep=lambda s: None)
    with pytest.raises(ShopifyError, match="doesn't exist"):
        client.query("query")


def test_missing_scope_is_explained(fake_session):
    session = fake_session([FakeResponse(403, {})])
    client = Shopify("demo.myshopify.com", "t", "2026-07", session=session)
    with pytest.raises(ShopifyError, match="access scope"):
        client.query("query")


def test_access_token_is_used_as_is():
    assert resolve_access_token("demo.myshopify.com", access_token="shpat_x") == "shpat_x"


def test_client_credentials_grant(fake_session):
    session = fake_session([FakeResponse(200, {"access_token": "minted"})])
    token = resolve_access_token("demo.myshopify.com", client_id="id", client_secret="s",
                                 session=session)
    assert token == "minted"
    assert session.calls[0][1]["data"]["grant_type"] == "client_credentials"


def test_shop_not_permitted_points_to_offline_token(fake_session):
    session = fake_session([FakeResponse(400, text="Oauth error shop_not_permitted")])
    with pytest.raises(ShopifyError, match="get_access_token.py"):
        resolve_access_token("demo.myshopify.com", client_id="id", client_secret="s",
                             session=session)
