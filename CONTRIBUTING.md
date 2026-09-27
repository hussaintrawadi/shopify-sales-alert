# Contributing

Thanks for helping. Small, focused pull requests are the easiest to review.

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
python scripts/demo.py   # renders email-preview.html from test data
```

The tests run without a Shopify store or an email account. Please keep it that way: anything that touches the network goes through `shopify.py` or `mailer.py`, and the tests swap those out.

## Ground rules

- **Read-only.** This project should never need a write scope on the store.
- **No new dependencies** unless there is no reasonable way around it. It runs on `requests` and `PyYAML`.
- **Settings are environment variables**, documented in the README table and in `.env.example`.
- **Emails must work in Gmail and Outlook.** That means inline styles and tables, no external CSS or scripts.
- **GraphQL changes** should be checked against the Admin API version in `config.py`, and stay under Shopify's query cost limit of 1,000 points.

## Reporting bugs

Open an issue with what you expected, what happened, and the log from the Actions run with any product names or email addresses removed.
