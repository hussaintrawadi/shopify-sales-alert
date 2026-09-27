import pytest

from conftest import FakeResponse
from sales_alert.mailer import MailError, parse_recipients, send, split_sender


def test_parse_recipients():
    assert parse_recipients("a@x.com, b@y.com") == ["a@x.com", "b@y.com"]
    assert parse_recipients("a@x.com;b@y.com;") == ["a@x.com", "b@y.com"]
    assert parse_recipients('["a@x.com", "b@y.com"]') == ["a@x.com", "b@y.com"]
    assert parse_recipients("") == []


def test_split_sender():
    assert split_sender("Stock Bot <bot@x.com>", "d") == ("Stock Bot", "bot@x.com")
    assert split_sender("bot@x.com", "Default") == ("Default", "bot@x.com")


def test_resend_payload(fake_session):
    session = fake_session([FakeResponse(200, {"id": "1"})])
    send("resend", sender="Bot <bot@x.com>", recipients=["a@x.com"], subject="S",
         html="<p>h</p>", text="t", api_key="re_key", session=session)
    url, kwargs = session.calls[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_key"
    assert kwargs["json"]["to"] == ["a@x.com"]


def test_brevo_payload_and_errors(fake_session):
    session = fake_session([FakeResponse(201, {}), FakeResponse(401, {}, text="bad key")])
    send("brevo", sender="Bot <bot@x.com>", recipients=["a@x.com"], subject="S",
         html="h", text="t", api_key="k", session=session)
    assert session.calls[0][1]["json"]["sender"] == {"name": "Bot", "email": "bot@x.com"}
    with pytest.raises(MailError, match="bad key"):
        send("brevo", sender="bot@x.com", recipients=["a@x.com"], subject="S", html="h",
             text="t", api_key="k", session=session)


def test_unknown_provider():
    with pytest.raises(MailError):
        send("fax", sender="a", recipients=["b"], subject="s", html="h", text="t")
