import json
from pathlib import Path
import tempfile

import pytest
from unittest.mock import MagicMock, patch
from grandma_gcn.gcn_stream import stream

from yarl import URL

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
    Test the run method of the GCN stream with a real notice
    """
    from grandma_gcn.gcn_stream.stream import GCNStream

    # Simulate a message queue
    message_queue = []

    mock_message_update = push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-update.json"
    )

    mock_message_retraction = push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "retraction.json"
    )

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

    mock_post_msg_on_slack = mocker.patch(
        "grandma_gcn.slackbot.gw_message.post_msg_on_slack"
    )

    mock_owncloud_mkdir_request = mocker.patch("requests.request")
    mock_owncloud_mkdir_request.return_value.status_code = (
        201  # Mock successful directory creation
    )

    # Mock gwemopt_task.s to avoid running the real Celery task
    mock_gwemopt_task = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.gwemopt_task", autospec=True
    )
    fake_signature = MagicMock()
    fake_signature.delay = MagicMock()
    fake_signature.apply_async = MagicMock()
    mock_gwemopt_task.s.return_value = fake_signature

    # Mock gwemopt_post_task to avoid running the real Celery chord callback
    mock_gwemopt_post_task = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.gwemopt_post_task", autospec=True
    )
    fake_post_signature = MagicMock()
    fake_post_signature.delay = MagicMock()
    fake_post_signature.apply_async = MagicMock()
    mock_gwemopt_post_task.s.return_value = fake_post_signature

    # Mock chord to avoid celery serialization issues
    mock_chord = mocker.patch("grandma_gcn.gcn_stream.consumer.chord", autospec=True)
    mock_chord.return_value = lambda *args, **kwargs: None

    # Create a temporary directory for saving notices
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock the GCNStream.notice_path attribute to use the temporary directory
        engine, session_local = sqlite_engine_and_session
        gcn_stream = GCNStream(
            gcn_config_path, engine, session_local, logger=logger, restart_queue=False
        )
        mocker.patch.object(gcn_stream, "notice_path", temp_path)

        # Run the GCN stream
        gcn_stream.run(test=True)

        # Assertions
        assert mock_poll_method.call_count == 3601
        mock_commit_method.assert_any_call(mock_message_update)
        mock_commit_method.assert_any_call(mock_message_retraction)
        mock_post_msg_on_slack.assert_called()  # Ensure post_msg_on_slack is called
        mock_gwemopt_task.s.assert_called()  # Ensure gwemopt_task.s is called
        mock_gwemopt_post_task.s.assert_called()  # Ensure gwemopt_post_task.s is called
        assert len(message_queue) == 0

        # Verify that the notice was saved to the temporary directory
        saved_files = list(temp_path.glob("*.json"))
        assert len(saved_files) == 1  # Ensure one file was saved
        with open(saved_files[0], "r") as f:
            saved_notice = json.load(f)
        assert saved_notice["superevent_id"] == "S241102br"  # Example assertion

        assert mock_owncloud_mkdir_request.call_count == 7
        _, kwargs = mock_owncloud_mkdir_request.call_args

        assert kwargs["method"] == "MKCOL"
        assert kwargs["url"] == URL(
            "https://owncloud.example.com/Candidates/GW/S241102br/VOEVENTS"
        )


def test_main_calls_gcnstream_and_run(tmp_path, sqlite_engine_and_session):
    # Création du fichier de config toml temporaire
    fake_config_path = tmp_path / "fake_config.toml"
    fake_config_path.write_text(
        "[PATH]\ngcn_stream_log_path='log.log'\nnotice_path='.'\n"
    )

    # Récupère engine et session_local depuis la fixture
    engine, session_local = sqlite_engine_and_session

    with (
        patch("grandma_gcn.gcn_stream.stream.init_logging") as mock_init_logging,
        patch("grandma_gcn.gcn_stream.stream.init_db") as mock_init_db,
        patch("grandma_gcn.gcn_stream.stream.GCNStream") as mock_gcnstream_cls,
    ):
        # Mock le logger
        mock_logger = MagicMock()
        mock_init_logging.return_value = mock_logger

        # Mock le retour de init_db avec la session/engine de la fixture
        mock_init_db.return_value = (engine, session_local)

        # Mock la classe GCNStream et sa méthode run
        mock_gcnstream = MagicMock()
        mock_gcnstream_cls.return_value = mock_gcnstream

        # Appelle la vraie fonction main (qui va utiliser tous les mocks)
        stream.main(gcn_config_path=str(fake_config_path))

        # Vérifications
        mock_init_logging.assert_called_once_with(logger_name="gcn_stream")
        mock_init_db.assert_called_once()
        mock_gcnstream_cls.assert_called_once()
        mock_gcnstream.run.assert_called_once()
