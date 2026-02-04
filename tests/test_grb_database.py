"""Tests for the GRB database model."""

from datetime import datetime, timezone

from grandma_gcn.database.grb_db import GRB_alert as GRB_alert_DB


def test_insert_grb_alert(sqlite_engine_and_session):
    """Test inserting a new GRB alert into the database."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert = GRB_alert_DB(
        triggerId="1423875",
        mission="Swift",
        packet_type=61,
        ra=123.456,
        dec=-45.678,
        error_deg=0.05,
        trigger_time=datetime(2025, 12, 14, 9, 2, 17, tzinfo=timezone.utc),
        xml_payload="<VOEvent>test</VOEvent>",
    )
    session.add(alert)
    session.commit()

    result = session.query(GRB_alert_DB).filter_by(triggerId="1423875").first()
    assert result is not None
    assert result.triggerId == "1423875"
    assert result.mission == "Swift"
    assert result.packet_type == 61
    assert result.ra == 123.456
    assert result.dec == -45.678
    assert result.reception_count == 1

    session.close()


def test_get_by_trigger_id_and_packet_type(sqlite_engine_and_session):
    """Test retrieving alert by trigger ID and packet type."""
    _, Session = sqlite_engine_and_session
    session = Session()

    # Insert multiple alerts with same trigger_id but different packet types
    alert1 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=61)
    alert2 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=67)
    alert3 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=81)
    session.add_all([alert1, alert2, alert3])
    session.commit()

    result = GRB_alert_DB.get_by_trigger_id_and_packet_type(session, "1423875", 67)
    assert result is not None
    assert result.packet_type == 67

    result = GRB_alert_DB.get_by_trigger_id_and_packet_type(session, "1423875", 99)
    assert result is None

    session.close()


def test_get_all_by_trigger_id(sqlite_engine_and_session):
    """Test retrieving all alerts for a trigger ID."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert1 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=61)
    alert2 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=67)
    alert3 = GRB_alert_DB(triggerId="9999999", mission="Swift", packet_type=61)
    session.add_all([alert1, alert2, alert3])
    session.commit()

    results = GRB_alert_DB.get_all_by_trigger_id(session, "1423875")
    assert len(results) == 2
    assert all(r.triggerId == "1423875" for r in results)

    session.close()


def test_get_last_by_trigger_id(sqlite_engine_and_session):
    """Test retrieving alert with highest reception count for a trigger ID."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert1 = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=61)
    session.add(alert1)
    session.commit()

    alert2 = GRB_alert_DB(
        triggerId="1423875", mission="Swift", packet_type=67, reception_count=5
    )
    session.add(alert2)
    session.commit()

    result = GRB_alert_DB.get_last_by_trigger_id(session, "1423875")
    assert result is not None
    assert result.packet_type == 67

    session.close()


def test_increment_reception_count(sqlite_engine_and_session):
    """Test incrementing reception count."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=61)
    session.add(alert)
    session.commit()

    assert alert.reception_count == 1

    alert.increment_reception_count(session)

    assert alert.reception_count == 2

    # Verify in DB
    result = session.query(GRB_alert_DB).filter_by(triggerId="1423875").first()
    assert result.reception_count == 2

    session.close()


def test_set_thread_ts(sqlite_engine_and_session):
    """Test setting thread timestamp."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert = GRB_alert_DB(triggerId="1423875", mission="Swift", packet_type=61)
    session.add(alert)
    session.commit()

    assert alert.thread_ts is None

    alert.set_thread_ts("1234567890.123456", session)

    assert alert.thread_ts == "1234567890.123456"

    # Verify in DB
    result = session.query(GRB_alert_DB).filter_by(triggerId="1423875").first()
    assert result.thread_ts == "1234567890.123456"

    session.close()


def test_get_or_create_creates_new(sqlite_engine_and_session):
    """Test get_or_create creates a new alert when none exists."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert = GRB_alert_DB.get_or_create(
        session=session,
        trigger_id="new_trigger",
        mission="SVOM",
        ra=100.0,
        dec=50.0,
        error_deg=0.1,
        trigger_time=datetime.now(timezone.utc),
        xml_payload="<xml>test</xml>",
    )

    assert alert is not None
    assert alert.triggerId == "new_trigger"
    assert alert.mission == "SVOM"
    assert alert.reception_count == 1

    session.close()


def test_get_or_create_returns_existing(sqlite_engine_and_session):
    """Test get_or_create returns existing alert."""
    _, Session = sqlite_engine_and_session
    session = Session()

    # Create initial alert
    initial = GRB_alert_DB(triggerId="existing", mission="Swift", packet_type=61)
    session.add(initial)
    session.commit()

    # Call get_or_create
    alert = GRB_alert_DB.get_or_create(
        session=session,
        trigger_id="existing",
        mission="Swift",
    )

    assert alert is not None
    assert alert.triggerId == "existing"
    # get_or_create returns existing without incrementing
    assert alert.reception_count == 1
    assert alert.id_grb == initial.id_grb  # Same record

    session.close()


def test_repr(sqlite_engine_and_session):
    """Test string representation of GRB_alert_DB."""
    _, Session = sqlite_engine_and_session
    session = Session()

    alert = GRB_alert_DB(
        triggerId="1423875",
        mission="Swift",
        packet_type=61,
        ra=123.456,
        dec=-45.678,
    )
    session.add(alert)
    session.commit()

    repr_str = repr(alert)
    assert "GRB_alert" in repr_str
    assert "1423875" in repr_str

    session.close()
