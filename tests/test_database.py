from grandma_gcn.database.gw_db import GW_alert


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
        GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts="123.456"
        )
        alert = GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts="123.456"
        )

        assert alert.triggerId == "S240707a"
        assert alert.reception_count == 2


def test_thread_ts_is_not_updated_on_increment(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts="original"
        )
        alert = GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts="new_value"
        )

        assert alert.reception_count == 2
        assert alert.thread_ts == "original"


def test_insert_with_none_thread_ts(sqlite_engine_and_session):
    _, SessionLocal = sqlite_engine_and_session

    with SessionLocal() as session:
        alert = GW_alert.insert_or_increment(
            session, trigger_id="S240707a", thread_ts=None
        )

        assert alert.triggerId == "S240707a"
        assert alert.thread_ts is None
        assert alert.reception_count == 1
