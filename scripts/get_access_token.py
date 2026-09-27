"""
Get a permanent (offline) Shopify Admin API access token, once, on your own computer.

You only need this when the client credentials grant does not work for you, which is
the case when the app and the store belong to different Shopify organizations (for
example, a client's store that installed your app through custom distribution).

Before you run it:
  1. In the Dev Dashboard, open your app and add this URL to its allowed redirect URLs:
         http://localhost:3456/callback
     then release a new version.
  2. Copy the app's Client ID and Client secret from its settings.

Run it (standard library only, nothing to install):
  export SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
  export SHOPIFY_CLIENT_ID=...
  export SHOPIFY_CLIENT_SECRET=...
  python3 scripts/get_access_token.py

A browser opens. Approve the app, and the token is printed in the terminal. Save it as
the SHOPIFY_ACCESS_TOKEN secret. It does not expire, so treat it like a password.
"""

import http.server
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

DEFAULT_SCOPES = "read_orders,read_products"

STORE = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip().lower()
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip()
SCOPES = os.environ.get("SHOPIFY_SCOPES", DEFAULT_SCOPES).strip()
PORT = int(os.environ.get("OAUTH_PORT", "3456"))
REDIRECT_URI = f"http://localhost:{PORT}/callback"
STATE = secrets.token_urlsafe(16)

result = {}


def exchange_code(code):
    body = urllib.parse.urlencode(
        {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code}).encode()
    request = urllib.request.Request(
        f"https://{STORE}/admin/oauth/access_token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode()).get("access_token")


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if params.get("state") != STATE:
            return self.reply("The state did not match, so the request was ignored.")
        if params.get("shop", "").lower() != STORE:
            return self.reply("This callback was for a different store, so it was ignored.")
        try:
            result["token"] = exchange_code(params.get("code", ""))
            self.reply("Done. You can close this tab and go back to the terminal.")
        except Exception as exc:  # noqa: BLE001 - shown to the person running the script
            result["token"] = None
            self.reply(f"Could not exchange the code for a token: {exc}")

    def reply(self, message):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;padding:2rem'>{message}</body></html>".encode())

    def log_message(self, *args):
        pass


def main():
    if not (STORE and CLIENT_ID and CLIENT_SECRET):
        sys.exit("Set SHOPIFY_STORE_DOMAIN, SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET first.")
    if not STORE.endswith(".myshopify.com"):
        sys.exit("SHOPIFY_STORE_DOMAIN should be the your-store.myshopify.com domain.")

    auth_url = f"https://{STORE}/admin/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        # No grant_options[] means an offline token, which does not expire.
    })
    print("Opening your browser to approve the app. If it does not open, visit:\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", PORT), CallbackHandler)
    while "token" not in result:
        server.handle_request()
    if not result["token"]:
        sys.exit("No token received. Check that the redirect URL is allowed in the app settings.")

    print("\nYour access token (save it as the SHOPIFY_ACCESS_TOKEN secret):\n")
    print(result["token"])


if __name__ == "__main__":
    main()
