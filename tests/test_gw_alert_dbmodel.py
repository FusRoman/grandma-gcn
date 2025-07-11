import io
import json

import pytest

from grandma_gcn.database.gw_db import GW_alert as DBGWAlert
from grandma_gcn.gcn_stream.gw_alert import GW_alert


def test_gw_alert_from_db_model_minimal():
    class DummyDBModel:
        payload_json = {
            "superevent_id": "S1",
            "event": {"significant": False},
            "alert_type": "INITIAL",
            "urls": {"gracedb": "url"},
        }

    thresholds = {
        "BBH_proba": 0.5,
        "Distance_cut": 100,
        "BNS_NSBH_size_cut": 100,
        "BBH_size_cut": 100,
    }
    alert = GW_alert.from_db_model(DummyDBModel(), thresholds)
    assert alert.event_id == "S1"
    assert alert.is_significant is False
    assert alert.event_type == GW_alert.EventType.INITIAL
    assert alert.gracedb_url == "url"


def make_db_model_from_notice_bytes(session, notice_bytes: bytes) -> DBGWAlert:
    # Load JSON from bytes and store as a JSON string in the DB
    notice_dict = json.load(io.BytesIO(notice_bytes))
    db_model = DBGWAlert(payload_json=notice_dict)
    session.add(db_model)
    session.commit()
    return db_model


def test_gw_alert_from_db_model_with_real_notice(
    sqlite_engine_and_session, path_tests, threshold_config
):
    # Use a real GCN notice (e.g. S241102br-initial.json)
    from tests.conftest import open_notice_file

    notice_bytes = open_notice_file(path_tests, "S241102br-initial.json")

    gw_alert = GW_alert(notice_bytes, thresholds=threshold_config)
    _, size_error, mean_dist, _ = gw_alert.get_error_region(0.9)

    _, SessionLocal = sqlite_engine_and_session
    with SessionLocal() as session:
        db_model = make_db_model_from_notice_bytes(session, notice_bytes)
        alert = GW_alert.from_db_model(db_model, threshold_config)
        _, size_error_alert, alert_dist, _ = alert.get_error_region(0.9)
        # Check a few key properties
        assert alert.event_id == "S241102br"
        assert alert.event_type == GW_alert.EventType.INITIAL
        assert alert.is_significant is True
        assert alert.gracedb_url.startswith(
            "https://gracedb.ligo.org/superevents/S241102br"
        )
        assert gw_alert.event_id == alert.event_id
        assert gw_alert.event_type == alert.event_type
        assert size_error == size_error_alert
        assert mean_dist == alert_dist


def make_fake_db_model_sqlite(session, payload_json: dict) -> DBGWAlert:
    # Insert a DB model in the sqlite session, store payload_json as a JSON string
    db_model = DBGWAlert(payload_json=payload_json)
    session.add(db_model)
    session.commit()
    return db_model


@pytest.fixture
def fake_db_model_dict():
    # Minimal dict matching the expected structure for GW_alert
    return {
        "superevent_id": "S999999xx",
        "event": {
            "time": "2025-01-01T00:00:00.000Z",
            "far": 1e-10,
            "properties": {"HasNS": 1.0, "HasRemnant": 0.5},
            "significant": True,
            "classification": {
                "BNS": 0.9,
                "BBH": 0.05,
                "NSBH": 0.05,
                "Terrestrial": 0.0,
            },
            "group": "CBC",
            "instruments": ["H1", "L1"],
            "skymap": "",  # base64 string, can be empty for this test
        },
        "alert_type": "INITIAL",
        "urls": {"gracedb": "https://gracedb.ligo.org/superevents/S999999xx/view/"},
    }


def test_gw_alert_from_db_model_sqlite(
    sqlite_engine_and_session, fake_db_model_dict, threshold_config
):
    # Test with a minimal fake DB model
    _, SessionLocal = sqlite_engine_and_session
    with SessionLocal() as session:
        db_model = make_fake_db_model_sqlite(session, fake_db_model_dict)
        alert = GW_alert.from_db_model(db_model, threshold_config)
        assert alert.event_id == "S999999xx"
        assert alert.event_type == GW_alert.EventType.INITIAL
        assert alert.far == 1e-10
        assert alert.has_NS == 1.0
        assert alert.has_remnant == 0.5
        assert alert.is_significant is True
        assert alert.event_class == GW_alert.CBC_proba.BNS
        assert alert.group == "CBC"
        assert alert.instruments == [GW_alert.Instrument.H1, GW_alert.Instrument.L1]
        assert (
            alert.gracedb_url == "https://gracedb.ligo.org/superevents/S999999xx/view/"
        )
