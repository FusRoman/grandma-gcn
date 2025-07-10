import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from yarl import URL

from grandma_gcn.gcn_stream import stream
from grandma_gcn.gcn_stream.consumer import Consumer
from grandma_gcn.gcn_stream.gcn_logging import init_logging
from tests.test_e2e import push_message_for_test


def test_init_gcn_stream(sqlite_engine_and_session, gcn_config_path, logger):
    """
    Test the initialization of the GCN stream
    """
    from grandma_gcn.gcn_stream.stream import GCNStream

    engine, session_local = sqlite_engine_and_session

    gcn_stream = GCNStream(
        gcn_config_path, engine, session_local, logger=logger, restart_queue=False
    )
    assert isinstance(gcn_stream, GCNStream)

    gcn_config = gcn_stream.gcn_config

    assert isinstance(gcn_config, dict)
    assert "CLIENT" in gcn_config
    assert "GCN_TOPICS" in gcn_config


def test_load_gcn_config(gcn_config_path, logger):
    """
    Test the loading of the GCN configuration
    """
    from grandma_gcn.gcn_stream.stream import load_gcn_config

    config = load_gcn_config(gcn_config_path, logger=logger)

    assert isinstance(config, dict)
    assert "CLIENT" in config
    assert "GCN_TOPICS" in config


@pytest.fixture
def mock_gcn_stream():
    class MockGCNStream:
        kafka_config = {}
        gcn_config = {
            "CLIENT": {"id": "test_id", "secret": "test_secret"},
            "KAFKA_CONFIG": {},
            "GCN_TOPICS": {"topics": ["test_topic"]},
            "Slack": {
                "gw_alert_channel": "test_channel",
                "gw_alert_channel_id": "test_channel_id",
            },
        }
        topics = {"test_topic": None}
        restart_queue = False
        logger = init_logging()

    return MockGCNStream()


def test_start_poll_loop(mocker, mock_gcn_stream):
    # Simulate a message queue
    message_queue = []

    # Create a mocked message
    mock_message = mocker.Mock()
    mock_message.topic.return_value = "test_topic"
    mock_message.offset.return_value = 42
    mock_message.error.return_value = None
    mock_message.value.return_value = b"test_message"

    # Add the mocked message to the queue
    message_queue.append(mock_message)

    # Mock the poll method
    def mock_poll(*args, **kwargs):
        return message_queue[0] if message_queue else None

    mock_poll_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.poll", side_effect=mock_poll
    )

    # Mock the commit method
    def mock_commit(message):
        if message in message_queue:
            message_queue.remove(message)

    mock_commit_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.commit", side_effect=mock_commit
    )

    # Mock the process_alert method
    mock_process_alert = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.Consumer.process_alert"
    )

    # Create an instance of the Consumer class
    consumer = Consumer(gcn_stream=mock_gcn_stream, logger=mock_gcn_stream.logger)

    # Call the start_poll_loop method
    consumer.start_poll_loop(interval_between_polls=1, max_retries=2)

    # Assertions
    assert mock_poll_method.call_count == 3  # Still unclear why it is called 3 times
    mock_commit_method.assert_called_once_with(mock_message)
    mock_process_alert.assert_called_once_with(notice=mock_message.value.return_value)
    assert len(message_queue) == 0


def test_gcn_stream_run(mocker, sqlite_engine_and_session, gcn_config_path, logger):
    """
    Test the run method of the GCN stream
    """
    from grandma_gcn.gcn_stream.stream import GCNStream

    # Simulate a message queue
    message_queue = []

    # Create a mocked message
    mock_message = mocker.Mock()
    mock_message.topic.return_value = "test_topic"
    mock_message.offset.return_value = 42
    mock_message.error.return_value = None
    mock_message.value.return_value = b"test_message"

    # Add the mocked message to the queue
    message_queue.append(mock_message)

    # Mock the poll method
    def mock_poll(*args, **kwargs):
        return message_queue[0] if message_queue else None

    mock_poll_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.poll", side_effect=mock_poll
    )

    # Mock the commit method
    def mock_commit(message):
        if message in message_queue:
            message_queue.remove(message)

    mock_commit_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.commit", side_effect=mock_commit
    )

    # Mock the process_alert method
    mock_process_alert = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.Consumer.process_alert"
    )

    engine, session_local = sqlite_engine_and_session
    gcn_stream = GCNStream(
        gcn_config_path, engine, session_local, logger=logger, restart_queue=False
    )

    # Run the GCN stream
    gcn_stream.run(test=True)

    # Assertions
    assert mock_poll_method.call_count == 3601
    mock_commit_method.assert_called_once_with(mock_message)
    mock_process_alert.assert_called_once_with(notice=mock_message.value.return_value)
    assert len(message_queue) == 0


def test_gcn_stream_with_real_notice(
    mocker, sqlite_engine_and_session, gcn_config_path, logger
):
    """
    Test the run method of the GCN stream with a real notice and database persistence
    """
    from grandma_gcn.database.gw_db import GW_alert
    from grandma_gcn.gcn_stream.stream import GCNStream

    # Simulate a message queue
    message_queue = []

    def push_update():
        return push_message_for_test(
            mocker, message_queue, "igwn.gwalert", "S241102br-update.json"
        )

    push_update()  # First alert
    _ = push_message_for_test(mocker, message_queue, "igwn.gwalert", "retraction.json")

    def mock_poll(*args, **kwargs):
        return message_queue[0] if message_queue else None

    _ = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.poll", side_effect=mock_poll
    )

    def mock_commit(message):
        if message in message_queue:
            message_queue.remove(message)

    _ = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.commit", side_effect=mock_commit
    )

    mock_post_msg_on_slack = mocker.patch(
        "grandma_gcn.slackbot.gw_message.post_msg_on_slack"
    )
    mock_post_msg_on_slack.return_value = {"ts": "123.456"}

    mock_owncloud_mkdir_request = mocker.patch("requests.request")
    mock_owncloud_mkdir_request.return_value.status_code = 201

    # Celery mocks
    mock_gwemopt_task = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.gwemopt_task", autospec=True
    )
    mock_gwemopt_task.s.return_value = MagicMock(
        apply_async=MagicMock(), delay=MagicMock()
    )

    mock_gwemopt_post_task = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.gwemopt_post_task", autospec=True
    )
    mock_gwemopt_post_task.s.return_value = MagicMock(
        apply_async=MagicMock(), delay=MagicMock()
    )

    mock_chord = mocker.patch("grandma_gcn.gcn_stream.consumer.chord", autospec=True)
    mock_chord.return_value = lambda *args, **kwargs: None

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        engine, session_local = sqlite_engine_and_session

        with session_local() as session:
            gcn_stream = GCNStream(
                gcn_config_path, engine, session, logger=logger, restart_queue=False
            )
            mocker.patch.object(gcn_stream, "notice_path", temp_path)

            # --- First run ---
            gcn_stream.run(test=True)

            alert = session.get(GW_alert, 1)
            assert alert is not None
            assert alert.triggerId == "S241102br"
            assert alert.thread_ts == "123.456"
            assert alert.reception_count == 1

            # Notice saved
            saved_files = list(temp_path.glob("*.json"))
            assert len(saved_files) == 1
            with open(saved_files[0]) as f:
                saved_notice = json.load(f)
            assert saved_notice["superevent_id"] == "S241102br"

            # Slack & OwnCloud interactions
            assert mock_post_msg_on_slack.called
            assert mock_owncloud_mkdir_request.call_count == 7
            _, kwargs = mock_owncloud_mkdir_request.call_args
            assert kwargs["method"] == "MKCOL"
            assert kwargs["url"] == URL(
                "https://owncloud.example.com/Candidates/GW/S241102br/VOEVENTS"
            )

        with session_local() as session:
            # --- Second run (same alert) ---
            push_update()  # Push same alert again
            gcn_stream.run(test=True)

            # --- Assertions after second alert ---
            alert = session.get(GW_alert, 2)
            assert alert is not None
            assert alert.triggerId == "S241102br"
            assert alert.reception_count == 2
            assert alert.thread_ts == "123.456"  # should not have changed


def test_main_calls_gcnstream_and_run(tmp_path, sqlite_engine_and_session):
    fake_config_path = tmp_path / "fake_config.toml"
    fake_config_path.write_text(
        "[PATH]\ngcn_stream_log_path='log.log'\nnotice_path='.'\n"
    )

    engine, session_local = sqlite_engine_and_session

    with (
        patch("grandma_gcn.gcn_stream.stream.init_logging") as mock_init_logging,
        patch("grandma_gcn.gcn_stream.stream.init_db") as mock_init_db,
        patch("grandma_gcn.gcn_stream.stream.GCNStream") as mock_gcnstream_cls,
        patch("grandma_gcn.gcn_stream.stream.dotenv_values") as mock_dotenv_values,
    ):
        mock_logger = MagicMock()
        mock_init_logging.return_value = mock_logger

        mock_init_db.return_value = (engine, session_local)

        mock_gcnstream = MagicMock()
        mock_gcnstream_cls.return_value = mock_gcnstream

        mock_dotenv_values.return_value = {
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
        }

        stream.main(gcn_config_path=str(fake_config_path))

        mock_init_logging.assert_called_once_with(logger_name="gcn_stream")
        mock_init_db.assert_called_once()
        mock_gcnstream_cls.assert_called_once()
        mock_gcnstream.run.assert_called_once()


def test_main_restart_queue_argument(tmp_path, sqlite_engine_and_session):
    """
    Test that the restart_queue argument is correctly passed from CLI to GCNStream
    """
    fake_config_path = tmp_path / "fake_config.toml"
    fake_config_path.write_text(
        "[PATH]\ngcn_stream_log_path='log.log'\nnotice_path='.'\n"
    )
    engine, session_local = sqlite_engine_and_session
    with (
        patch("grandma_gcn.gcn_stream.stream.init_logging") as mock_init_logging,
        patch("grandma_gcn.gcn_stream.stream.init_db") as mock_init_db,
        patch("grandma_gcn.gcn_stream.stream.GCNStream") as mock_gcnstream_cls,
        patch("grandma_gcn.gcn_stream.stream.dotenv_values") as mock_dotenv_values,
    ):
        mock_logger = MagicMock()
        mock_init_logging.return_value = mock_logger
        mock_init_db.return_value = (engine, session_local)
        mock_gcnstream = MagicMock()
        mock_gcnstream_cls.return_value = mock_gcnstream
        mock_dotenv_values.return_value = {
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
        }
        # Test default (should be False)
        stream.main(gcn_config_path=str(fake_config_path))
        _, kwargs = mock_gcnstream_cls.call_args
        assert kwargs.get("restart_queue", False) is False
        # Test with restart_queue True
        stream.main(gcn_config_path=str(fake_config_path), restart_queue=True)
        _, kwargs = mock_gcnstream_cls.call_args
        assert kwargs.get("restart_queue", False) is True

@pytest.mark.usefixtures("sqlite_engine_and_session")
def test_handle_significant_alert_db_and_slack(
    mocker, sqlite_engine_and_session, logger, threshold_config
):
    """
    Teste la création et la mise à jour d'une alerte GW dans la base via _handle_significant_alert,
    en mockant la partie Slack et Owncloud, et vérifie la présence de la notice en base.
    """
    from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB
    from grandma_gcn.gcn_stream.consumer import Consumer
    from grandma_gcn.gcn_stream.gw_alert import GW_alert

    # Prépare une fausse config et session
    _, SessionLocal = sqlite_engine_and_session
    session = SessionLocal()

    class DummyStream:
        session_local = session
        gcn_config = {
            "Slack": {"gw_alert_channel": "chan", "gw_alert_channel_id": "id"},
            "OWNCLOUD": {},
            "THRESHOLD": threshold_config,
            "KAFKA_CONFIG": {},
            "CLIENT": {"id": "dummy", "secret": "dummy"},
            "GCN_TOPICS": {"topics": ["dummy_topic"]},
        }
        slack_client = None
        restart_queue = False

    # Mock Slack et Owncloud
    mocker.patch(
        "grandma_gcn.gcn_stream.consumer.new_alert_on_slack",
        return_value={"ts": "123.456"},
    )
    mocker.patch.object(
        Consumer,
        "init_owncloud_folders",
        return_value=("/fake/path", "https://owncloud/fake"),
    )

    consumer = Consumer(gcn_stream=DummyStream(), logger=logger)

    # Notice GW minimal
    notice = b'{"superevent_id": "S240707a", "alert_type": "INITIAL", "event": {"significant": true}}'
    gw_alert = GW_alert(notice, threshold_config)

    # Premier appel : création
    url, ts = consumer._handle_significant_alert(gw_alert)
    alert = GW_alert_DB.get_last_by_trigger_id(session, "S240707a")
    assert alert is not None
    assert alert.thread_ts == "123.456"
    assert alert.reception_count == 1
    assert url == "https://owncloud/fake"
    assert ts == "123.456"

    # Vérifie que la notice est bien présente en base
    alert_db = GW_alert_DB.get_last_by_trigger_id(session, "S240707a")
    assert alert_db is not None
    assert alert_db.payload_json is not None
    assert alert_db.payload_json["superevent_id"] == "S240707a"

    # Deuxième appel : incrémentation
    url2, ts2 = consumer._handle_significant_alert(gw_alert)
    alert2 = GW_alert_DB.get_last_by_trigger_id(session, "S240707a")
    assert alert2.reception_count == 2
    assert alert2.thread_ts == "123.456"
    assert url2 == "https://owncloud/fake"
    assert ts2 == "123.456"

    session.close()
