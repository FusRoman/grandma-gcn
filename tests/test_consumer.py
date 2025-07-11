from unittest.mock import MagicMock

from grandma_gcn.database.gw_db import GW_alert as DBGWAlert
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.gcn_stream.stream import GCNStream


def fake_notice_bytes(triggerId):
    import json

    d = {
        "superevent_id": triggerId,
        "event": {
            "significant": True,
            "skymap": "",
            "instruments": ["H1"],
            "classification": {"BNS": 1.0},
        },
        "alert_type": "INITIAL",
        "urls": {"gracedb": "url"},
    }
    return json.dumps(d).encode("utf-8")


def test_handle_significant_alert_thread_and_message_ts(
    sqlite_engine_and_session, threshold_config, gcn_config_path, mocker
):
    engine, SessionLocal = sqlite_engine_and_session
    with SessionLocal() as session:
        # Setup dummy slack client and logger
        slack_client = MagicMock()
        logger = MagicMock()
        slack_client.send_message = MagicMock()

        def slack_side_effect(*args, **kwargs):
            if "thread_ts" not in kwargs or kwargs["thread_ts"] is None:
                slack_side_effect.thread_count += 1
                return {"ts": f"thread-{slack_side_effect.thread_count}"}
            else:
                slack_side_effect.msg_count += 1
                return {"ts": f"msg-{slack_side_effect.msg_count}"}

        slack_side_effect.thread_count = 0
        slack_side_effect.msg_count = 0

        mocker.patch(
            "grandma_gcn.gcn_stream.consumer.new_alert_on_slack",
            side_effect=slack_side_effect,
        )
        mocker.patch(
            "grandma_gcn.gcn_stream.consumer.build_gwalert_notification_msg",
            MagicMock(),
        )
        mocker.patch(
            "grandma_gcn.gcn_stream.consumer.build_gwalert_data_msg", MagicMock()
        )
        mocker.patch("grandma_gcn.gcn_stream.consumer.OwncloudClient", MagicMock())
        mocker.patch(
            "grandma_gcn.gcn_stream.consumer.Consumer.init_owncloud_folders",
            MagicMock(return_value=("/fake/path", "owncloud-url")),
        )

        gcn_stream = GCNStream(
            gcn_config_path, engine, session, logger=logger, restart_queue=False
        )
        import grandma_gcn.gcn_stream.consumer as consumer_mod

        consumer = consumer_mod.Consumer(gcn_stream, logger)

        # First alert
        alert1 = GW_alert(fake_notice_bytes("S999999xx"), threshold_config)
        consumer._handle_significant_alert(alert1, False)
        db_alert1 = DBGWAlert.get_last_by_trigger_id(session, "S999999xx")
        assert db_alert1.thread_ts == "thread-1"
        assert db_alert1.message_ts == "msg-1"

        # Other alert
        alert_other = GW_alert(fake_notice_bytes("S111111xx"), threshold_config)
        consumer._handle_significant_alert(alert_other, False)
        db_alert_other = DBGWAlert.get_last_by_trigger_id(session, "S111111xx")
        assert db_alert_other.thread_ts == "thread-2"
        assert db_alert_other.message_ts == "msg-2"

        # Second alert with same triggerId
        alert2 = GW_alert(fake_notice_bytes("S999999xx"), threshold_config)
        consumer._handle_significant_alert(alert2, False)
        db_alert2 = DBGWAlert.get_last_by_trigger_id(session, "S999999xx")
        assert db_alert2.thread_ts == "thread-1"
        assert db_alert2.message_ts == "msg-3"
        assert db_alert1.thread_ts == db_alert2.thread_ts
        assert db_alert1.message_ts != db_alert2.message_ts
