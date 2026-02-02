"""Tests for GRB alert processing in consumer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from grandma_gcn.gcn_stream.consumer import Consumer
from grandma_gcn.gcn_stream.grb_alert import Mission
from grandma_gcn.gcn_stream.stream import load_gcn_config
from tests.conftest import open_notice_file


@pytest.fixture
def mock_gcn_stream(sqlite_engine_and_session, logger):
    """Create a mock GCN stream for testing."""
    _, Session = sqlite_engine_and_session
    mock_stream = MagicMock()
    mock_stream.gcn_config = load_gcn_config(
        Path("tests/gcn_stream_test.toml"), logger=logger
    )
    mock_stream.session_local = Session()
    mock_stream.slack_client = MagicMock()
    return mock_stream


class TestTopicRouting:
    """Tests for topic-based routing in process_alert."""

    def test_swift_topic_routes_to_grb(self, mock_gcn_stream, logger, path_tests):
        """Test that Swift topic routes to GRB processing."""
        consumer = Consumer(gcn_stream=mock_gcn_stream, logger=logger)

        with patch.object(consumer, "_process_grb_alert") as mock_grb:
            with patch.object(consumer, "_process_gw_alert") as mock_gw:
                notice = open_notice_file(path_tests, "swift_bat_type61.xml")
                consumer.process_alert(
                    notice, topic="gcn.classic.voevent.SWIFT_BAT_GRB_POS_ACK"
                )

                mock_grb.assert_called_once()
                mock_gw.assert_not_called()
                call_args = mock_grb.call_args
                assert call_args[0][1] == Mission.SWIFT

    def test_svom_topic_routes_to_grb(self, mock_gcn_stream, logger, path_tests):
        """Test that SVOM topic routes to GRB processing."""
        consumer = Consumer(gcn_stream=mock_gcn_stream, logger=logger)

        with patch.object(consumer, "_process_grb_alert") as mock_grb:
            with patch.object(consumer, "_process_gw_alert") as mock_gw:
                notice = open_notice_file(path_tests, "svom_eclairs.xml")
                consumer.process_alert(notice, topic="gcn.notices.svom.voevent.eclairs")

                mock_grb.assert_called_once()
                mock_gw.assert_not_called()
                call_args = mock_grb.call_args
                assert call_args[0][1] == Mission.SVOM

    def test_gw_topic_routes_to_gw(self, mock_gcn_stream, logger, path_tests):
        """Test that GW topic routes to GW processing."""
        consumer = Consumer(gcn_stream=mock_gcn_stream, logger=logger)

        with patch.object(consumer, "_process_grb_alert") as mock_grb:
            with patch.object(consumer, "_process_gw_alert") as mock_gw:
                notice = open_notice_file(path_tests, "S241102br-update.json")
                consumer.process_alert(notice, topic="igwn.gwalert")

                mock_gw.assert_called_once()
                mock_grb.assert_not_called()


class TestGRBAlertProcessing:
    """Tests for _process_grb_alert method."""

    def test_process_swift_alert_saves_to_db(
        self, mock_gcn_stream, logger, path_tests, sqlite_engine_and_session
    ):
        """Test that Swift alert is saved to database."""
        from grandma_gcn.database.grb_db import GRB_alert as GRB_alert_DB

        _, Session = sqlite_engine_and_session
        session = Session()
        mock_gcn_stream.session_local = session

        consumer = Consumer(gcn_stream=mock_gcn_stream, logger=logger)

        with patch(
            "grandma_gcn.gcn_stream.consumer.send_grb_alert_to_slack"
        ) as mock_slack:
            mock_slack.return_value = {"ts": "1234567890.123456"}

            notice = open_notice_file(path_tests, "swift_bat_type61.xml")
            consumer._process_grb_alert(notice, Mission.SWIFT)

        result = session.query(GRB_alert_DB).filter_by(triggerId="1423875").first()
        assert result is not None
        assert result.mission == "Swift"
        assert result.packet_type == 61
        session.close()

    def test_process_svom_alert_saves_to_db(
        self, mock_gcn_stream, logger, path_tests, sqlite_engine_and_session
    ):
        """Test that SVOM alert is saved to database."""
        from grandma_gcn.database.grb_db import GRB_alert as GRB_alert_DB

        _, Session = sqlite_engine_and_session
        session = Session()
        mock_gcn_stream.session_local = session

        consumer = Consumer(gcn_stream=mock_gcn_stream, logger=logger)

        with patch(
            "grandma_gcn.gcn_stream.consumer.send_grb_alert_to_slack"
        ) as mock_slack:
            mock_slack.return_value = {"ts": "1234567890.123456"}

            notice = open_notice_file(path_tests, "svom_eclairs.xml")
            consumer._process_grb_alert(notice, Mission.SVOM)

        result = session.query(GRB_alert_DB).filter_by(triggerId="sb25120806").first()
        assert result is not None
        assert result.mission == "SVOM"
        assert result.packet_type == 202
        session.close()
