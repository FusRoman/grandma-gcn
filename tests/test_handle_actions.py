import json
import time

import pytest

from grandma_gcn.flask_listener.app_factory import create_app


@pytest.fixture
def app(monkeypatch):
    # Patch DB session
    class DummySession:
        def close(self):
            pass

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.get_session_local",
        lambda: lambda: DummySession(),
    )
    # Patch slackbot
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.init_slackbot",
        lambda: DummySlackClient(),
    )
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testkey",
            "SLACK_SIGNING_SECRET": "changeme",
            "GCN_CONFIG": {
                "THRESHOLD": 0.5,
                "Slack": {"gw_alert_channel": "C123", "gw_alert_channel_id": "C123id"},
            },
        }
    )
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


class DummySlackClient:
    def conversations_open(self, users):
        return {"channel": {"id": "C123"}}

    def chat_postMessage(self, channel, text):
        return {"ok": True}


class DummyGWAlertDB:
    triggerId = "S123"
    is_process_running = False
    thread_ts = "123.456"

    @staticmethod
    def get_by_message_ts(session, ts):
        return DummyGWAlertDB()


class DummyGWAlert:
    @staticmethod
    def from_db_model(db, thresholds):
        return "dummy_gw_alert"


def dummy_new_alert_on_slack(*args, **kwargs):
    return None


def dummy_automatic_gwemopt_process(*args, **kwargs):
    return None


def test_handle_actions_success(client, monkeypatch):
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.GW_alert_DB", DummyGWAlertDB
    )
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.GW_alert", DummyGWAlert
    )
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.new_alert_on_slack",
        dummy_new_alert_on_slack,
    )
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.automatic_gwemopt_process",
        dummy_automatic_gwemopt_process,
    )
    # Mock verify_slack_request to always return True
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.verify_slack_request",
        lambda *a, **kw: True,
    )
    payload_dict = {
        "actions": [{"action_id": "run_obs_plan"}],
        "user": {"username": "testuser", "id": "U123"},
        "message": {"ts": "123.456"},
    }
    payload = json.dumps(payload_dict, separators=(",", ":"))
    from urllib.parse import urlencode

    form_body = urlencode({"payload": payload})
    timestamp = str(int(time.time()))
    headers = {
        "X-Slack-Signature": "any",
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = client.post(
        "/api/slack/actions", data=form_body.encode("utf-8"), headers=headers
    )
    print(response.get_json())
    assert response.status_code == 200
    assert "Running observation plan" in response.get_json()["text"]


def test_handle_actions_invalid_signature(client):
    # Mock verify_slack_request to always return False
    from urllib.parse import urlencode

    payload_dict = {
        "actions": [{"action_id": "run_obs_plan"}],
        "user": {"username": "testuser", "id": "U123"},
        "message": {"ts": "123.456"},
    }
    payload = json.dumps(payload_dict, separators=(",", ":"))
    form_body = urlencode({"payload": payload})
    headers = {
        "X-Slack-Signature": "invalid",
        "X-Slack-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    import grandma_gcn.flask_listener.slack_listener as slack_listener

    slack_listener.verify_slack_request = lambda *a, **kw: False
    response = client.post(
        "/api/slack/actions", data=form_body.encode("utf-8"), headers=headers
    )
    assert response.status_code == 400
    assert b"Invalid Slack signature" in response.data


def test_handle_actions_exception(client, monkeypatch):
    def raise_exc(*a, **kw):
        raise Exception("fail")

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.GW_alert_DB", DummyGWAlertDB
    )
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.GW_alert", DummyGWAlert
    )
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.new_alert_on_slack", raise_exc
    )
    # Mock verify_slack_request to always return True
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.verify_slack_request",
        lambda *a, **kw: True,
    )
    payload_dict = {
        "actions": [{"action_id": "run_obs_plan"}],
        "user": {"username": "testuser", "id": "U123"},
        "message": {"ts": "123.456"},
    }
    payload = json.dumps(payload_dict, separators=(",", ":"))
    from urllib.parse import urlencode

    form_body = urlencode({"payload": payload})
    timestamp = str(int(time.time()))
    headers = {
        "X-Slack-Signature": "any",
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = client.post(
        "/api/slack/actions", data=form_body.encode("utf-8"), headers=headers
    )
    assert response.status_code == 500
    assert b"Internal error" in response.data


def test_handle_actions_db_integration(client, monkeypatch, sqlite_engine_and_session):
    """
    Teste que handle_actions récupère bien l'alerte en base et passe les bons paramètres à automatic_gwemopt_process.
    """
    # --- Setup DB ---
    from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB

    _, SessionLocal = sqlite_engine_and_session
    with SessionLocal() as session:
        alert = GW_alert_DB(
            triggerId="S999",
            thread_ts="999.888",
            message_ts="999.888",
            is_process_running=False,
            reception_count=1,
            payload_json={
                "superevent_id": "S999"
            },  # champ minimal pour GW_alert.from_db_model
        )
        session.add(alert)
        session.commit()

    # --- Patch DB session in Flask context ---
    # Patch get_session_local to return a function that creates a session instance
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.get_session_local",
        lambda: lambda: SessionLocal(),
    )

    # --- Patch Slackbot ---
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.init_slackbot",
        lambda: DummySlackClient(),
    )

    # --- Patch verify_slack_request ---
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.verify_slack_request",
        lambda *a, **kw: True,
    )

    # --- Patch new_alert_on_slack (no-op) ---
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.new_alert_on_slack",
        lambda *a, **kw: None,
    )

    # --- Patch automatic_gwemopt_process to capture call ---
    call_args = {}

    def capture_automatic_gwemopt_process(*args, **kwargs):
        call_args["args"] = args
        call_args["kwargs"] = kwargs
        return None

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.automatic_gwemopt_process",
        capture_automatic_gwemopt_process,
    )

    # --- Prepare payload ---
    payload_dict = {
        "actions": [{"action_id": "run_obs_plan"}],
        "user": {"username": "testuser", "id": "U999"},
        "message": {"ts": "999.888"},
    }
    payload = json.dumps(payload_dict, separators=(",", ":"))
    from urllib.parse import urlencode

    form_body = urlencode({"payload": payload})
    timestamp = str(int(time.time()))
    headers = {
        "X-Slack-Signature": "any",
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # --- Call route ---
    response = client.post(
        "/api/slack/actions", data=form_body.encode("utf-8"), headers=headers
    )
    assert response.status_code == 200
    # --- Check that automatic_gwemopt_process was called with the DB alert ---
    assert call_args["args"], "automatic_gwemopt_process has not been called"
    # GW_alert_DB instance should be 2nd arg
    gw_alert_db_arg = call_args["args"][1]
    assert hasattr(gw_alert_db_arg, "triggerId")
    assert gw_alert_db_arg.triggerId == "S999"
    # The session should be a SQLAlchemy session
    assert hasattr(call_args["args"][2], "commit")
    # The channel and channel_id should match config
    assert call_args["args"][4] == "C123"
    assert call_args["args"][5] == "C123id"


def test_handle_actions_ignored_action(client, monkeypatch):
    """
    Verify that the handler ignores actions with unexpected action_id.
    """
    # Patch verify_slack_request to always return True
    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.verify_slack_request",
        lambda *a, **kw: True,
    )

    # Patch automatic_gwemopt_process to ensure it is NOT called
    called = {}

    def fake_automatic_gwemopt_process(*args, **kwargs):
        called["was_called"] = True

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.slack_listener.automatic_gwemopt_process",
        fake_automatic_gwemopt_process,
    )

    # Payload with an action_id that should be ignored
    payload_dict = {
        "actions": [{"action_id": "some_other_action"}],
        "user": {"username": "testuser", "id": "U123"},
        "message": {"ts": "123.456"},
    }
    from urllib.parse import urlencode

    payload = json.dumps(payload_dict, separators=(",", ":"))
    form_body = urlencode({"payload": payload})
    headers = {
        "X-Slack-Signature": "any",
        "X-Slack-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Call the endpoint
    response = client.post(
        "/api/slack/actions", data=form_body.encode("utf-8"), headers=headers
    )

    # Assert that the action was ignored
    assert response.status_code == 200
    data = response.get_json()
    assert "ignored" in data["text"].lower()

    # Ensure automatic_gwemopt_process was NOT called
    assert "was_called" not in called
