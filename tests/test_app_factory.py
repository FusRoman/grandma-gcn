import pytest
from flask import Flask

from grandma_gcn.flask_listener.app_factory import create_app


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "testkey"})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_app_creation(app):
    assert isinstance(app, Flask)
    assert app.config["SECRET_KEY"] == "testkey"
    assert app.config["TESTING"] is True


def test_ping_route(client, monkeypatch):
    # Patch DB session to avoid real DB connection
    class DummySession:
        def close(self):
            pass

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.get_session_local",
        lambda: lambda: DummySession(),
    )
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.get_json() == {"message": "pong"}


def test_index_route(client, monkeypatch):
    class DummySession:
        def close(self):
            pass

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.get_session_local",
        lambda: lambda: DummySession(),
    )
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Hello from grandma-bot !"}


def test_db_ping_route(client, monkeypatch):
    class DummyDB:
        def execute(self, *args, **kwargs):
            class Result:
                def scalar(self):
                    return 1

            return Result()

        def close(self):
            pass

    monkeypatch.setattr(
        "grandma_gcn.flask_listener.app_factory.get_session_local",
        lambda: lambda: DummyDB(),
    )
    response = client.get("/db-ping")
    assert response.status_code == 200
    assert response.get_json() == {"db_status": 1}
