import hashlib
import hmac
import time

import pytest
from flask import Flask, g

from grandma_gcn.flask_listener.slack_listener import verify_slack_request


class DummyRequest:
    def __init__(self, data, signature, timestamp):
        self._data = data
        self.headers = {
            "X-Slack-Signature": signature,
            "X-Slack-Request-Timestamp": timestamp,
        }

    def get_data(self, as_text=False):
        return self._data if as_text else self._data.encode()


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.app_context():
        yield app


def make_signature(secret, timestamp, data):
    base_string = f"v0:{timestamp}:{data}"
    sig = (
        "v0="
        + hmac.new(secret.encode(), base_string.encode(), hashlib.sha256).hexdigest()
    )
    return sig


def test_valid_signature(app_ctx):
    g.slack_secret = "testsecret"
    timestamp = str(int(time.time()))
    data = "payload=test"
    sig = make_signature(g.slack_secret, timestamp, data)
    req = DummyRequest(data, sig, timestamp)
    assert verify_slack_request(req) is True


def test_invalid_signature(app_ctx):
    g.slack_secret = "testsecret"
    timestamp = str(int(time.time()))
    data = "payload=test"
    sig = "v0=invalidsig"
    req = DummyRequest(data, sig, timestamp)
    assert verify_slack_request(req) is False


def test_old_timestamp(app_ctx):
    g.slack_secret = "testsecret"
    timestamp = str(int(time.time()) - 4000)  # > 5 min old
    data = "payload=test"
    sig = make_signature(g.slack_secret, timestamp, data)
    req = DummyRequest(data, sig, timestamp)
    assert verify_slack_request(req) is False


def test_invalid_timestamp_format(app_ctx):
    g.slack_secret = "testsecret"
    timestamp = "notanumber"
    data = "payload=test"
    sig = make_signature(g.slack_secret, timestamp, data)
    req = DummyRequest(data, sig, timestamp)
    assert verify_slack_request(req) is False
