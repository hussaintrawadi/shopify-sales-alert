"""A small Shopify Admin GraphQL client: getting a token, retries and pagination."""

import time

import requests

MAX_ATTEMPTS = 6


class ShopifyError(RuntimeError):
    """Raised when Shopify refuses a request or keeps failing."""


def resolve_access_token(store_domain, *, access_token=None, client_id=None,
                         client_secret=None, user_agent="shopify-automation", session=None):
    """Return an Admin API access token for the store.

    A token in SHOPIFY_ACCESS_TOKEN is used as it is. Otherwise a fresh one is minted
    with the client credentials grant, which works for a Dev Dashboard app installed
    on a store in the same Shopify organization. Those tokens last 24 hours, so every
    run mints a new one.
    """
    if access_token:
        return access_token
    if not (client_id and client_secret):
        raise ShopifyError(
            "No Shopify credentials. Set SHOPIFY_ACCESS_TOKEN, or both "
            "SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET.")

    http = session or requests
    resp = http.post(
        f"https://{store_domain}/admin/oauth/access_token",
        data={"client_id": client_id, "client_secret": client_secret,
              "grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    if resp.status_code == 400 and "shop_not_permitted" in resp.text:
        raise ShopifyError(
            "Shopify refused the client credentials grant (shop_not_permitted). It only "
            "works when the app and the store are in the same organization. Run "
            "scripts/get_access_token.py once and put the token in SHOPIFY_ACCESS_TOKEN.")
    if resp.status_code >= 400:
        raise ShopifyError(f"Token request failed: HTTP {resp.status_code} {resp.text[:300]}")
    token = resp.json().get("access_token")
    if not token:
        raise ShopifyError(f"The token response had no access_token: {resp.text[:300]}")
    return token


class Shopify:
    """Runs GraphQL queries against one store, backing off when throttled."""

    def __init__(self, store_domain, token, api_version, *, user_agent="shopify-automation",
                 session=None, sleep=time.sleep):
        self.url = f"https://{store_domain}/admin/api/{api_version}/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
        self.session = session or requests.Session()
        self.sleep = sleep

    def query(self, document, variables=None):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            resp = self.session.post(
                self.url, json={"query": document, "variables": variables or {}},
                headers=self.headers, timeout=60)

            if resp.status_code == 429 or resp.status_code >= 500:
                self._wait(attempt)
                continue
            if resp.status_code == 401:
                raise ShopifyError(
                    "Shopify rejected the access token (HTTP 401). Check the token and "
                    "SHOPIFY_STORE_DOMAIN.")
            if resp.status_code == 403:
                raise ShopifyError(
                    "Shopify returned HTTP 403. The app is most likely missing an access "
                    "scope. The README lists the scopes this project needs.")
            if resp.status_code >= 400:
                raise ShopifyError(f"Shopify returned HTTP {resp.status_code}: {resp.text[:300]}")

            body = resp.json()
            errors = body.get("errors")
            if isinstance(errors, str):
                raise ShopifyError(f"Shopify error: {errors}")
            if errors:
                if any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors):
                    self._wait(attempt)
                    continue
                messages = "; ".join(e.get("message", str(e)) for e in errors)
                raise ShopifyError(f"GraphQL error: {messages}")
            return body["data"]

        raise ShopifyError(f"Shopify kept throttling or failing after {MAX_ATTEMPTS} attempts.")

    def paginate(self, document, root, variables=None):
        """Yield every node of the connection at data[root], page by page."""
        cursor = None
        while True:
            connection = self.query(document, {**(variables or {}), "cursor": cursor})[root]
            yield from connection["nodes"]
            page = connection["pageInfo"]
            if not page["hasNextPage"]:
                return
            cursor = page["endCursor"]

    def shop(self):
        return self.query("query { shop { name currencyCode ianaTimezone } }")["shop"]

    def _wait(self, attempt):
        self.sleep(min(2 ** attempt, 30))
