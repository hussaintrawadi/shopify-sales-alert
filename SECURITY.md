# Security

This project reads your store's orders and products and sends an email. It never writes to your store: the scopes it needs are read-only.

## Reporting a problem

Please open a [security advisory](https://github.com/hussaintrawadi/shopify-sales-alert/security/advisories/new) rather than a public issue, and allow some time for a fix before sharing details.

## Keeping your copy safe

- Put every credential in GitHub Actions secrets or a local `.env` file. `.env` is git-ignored on purpose. Never commit a token, client secret or email API key.
- An offline token from `scripts/get_access_token.py` does not expire. Treat it like a password, and uninstall the app from the store if it ever leaks.
- Give the Shopify app only `read_orders` and `read_products`. It needs nothing else.
- Keep your copy of the repository private. Workflow logs include your daily revenue in the email subject.
