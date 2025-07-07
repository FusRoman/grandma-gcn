from unittest.mock import MagicMock
import pytest
from sqlalchemy import text
from grandma_gcn.database.gw_db import GW_alert
from grandma_gcn.database.init_db import init_db


def test_insert_first_alert(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        alert = GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts="123.456"
        )

        assert alert.triggerId == "S240707a"
        assert alert.thread_ts == "123.456"
        assert alert.reception_count == 1


def test_insert_duplicate_alert_increments_count(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        GW_alert.insert_or_increment(session, "S240707a", thread_ts="123.456")
        alert = GW_alert.insert_or_increment(session, "S240707a", thread_ts="123.456")

        assert alert.reception_count == 2


def test_thread_ts_is_not_updated_on_increment(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        GW_alert.insert_or_increment(session, "S240707a", thread_ts="original")
        alert = GW_alert.insert_or_increment(session, "S240707a", thread_ts="new_value")

        assert alert.reception_count == 2
        assert alert.thread_ts == "original"


def test_insert_with_none_thread_ts(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        alert = GW_alert.insert_or_increment(session, "S240707b", thread_ts=None)

        assert alert.triggerId == "S240707b"
        assert alert.thread_ts is None
        assert alert.reception_count == 1


def test_get_or_set_thread_ts_sets_only_if_none(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        alert = GW_alert.get_by_trigger_id(session, "UNKNOWN")
        assert alert is None

        result = GW_alert.get_or_set_thread_ts(session, "UNKNOWN", "789.000")
        assert result is None or isinstance(result, GW_alert)

    with SessionLocal() as session:
        alert = GW_alert(triggerId="S240707c", thread_ts=None)
        session.add(alert)
        session.commit()

        updated = GW_alert.get_or_set_thread_ts(session, "S240707c", "789.000")
        assert updated is not None
        assert updated.thread_ts == "789.000"

        updated = GW_alert.get_or_set_thread_ts(
            session, "S240707c", "should_not_overwrite"
        )
        assert updated.thread_ts == "789.000"


def test_increment_reception_count_instance_method(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        alert = GW_alert.get_or_create(session, "S240707d", thread_ts="init")
        assert alert.reception_count == 1

        alert.increment_reception_count(session)
        assert alert.reception_count == 2


def test_init_db_with_sqlite_memory(logger):
    database_url = "sqlite:///:memory:"
    engine, SessionLocal = init_db(database_url, logger=logger, echo=True)

    # Vérifie que l'engine fonctionne
    assert engine is not None
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

    # Vérifie que la session fonctionne
    with SessionLocal() as session:
        assert session is not None


def test_init_db_raises_with_bad_url():
    with pytest.raises(Exception):
        init_db(
            "postgresql://invalid:invalid@localhost:9999/doesnotexist",
            logger=MagicMock(),
        )
