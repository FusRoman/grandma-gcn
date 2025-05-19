from pathlib import Path

import pytest

from grandma_gcn.gcn_stream.consumer import Consumer
from grandma_gcn.gcn_stream.gcn_logging import init_logging


@pytest.fixture
def logger():
    """
    Fixture to initialize the logger
    """
    return init_logging()


@pytest.fixture
def gcn_config_path():
    """
    Fixture to provide the path to the GCN configuration file
    """
    return Path("tests/gcn_stream_test.toml")


def test_init_gcn_stream(gcn_config_path, logger):
    """
    Test the initialization of the GCN stream
    """
    from grandma_gcn.gcn_stream.stream import GCNStream

    gcn_stream = GCNStream(gcn_config_path, logger=logger, restart_queue=False)
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
        }
        topics = {"test_topic": None}
        restart_queue = False

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

    # Create an instance of the Consumer class
    consumer = Consumer(gcn_stream=mock_gcn_stream)

    # Call the start_poll_loop method
    consumer.start_poll_loop(interval_between_polls=1, max_retries=2)

    # Assertions
    assert mock_poll_method.call_count == 3  # Still unclear why it is called 3 times
    mock_commit_method.assert_called_once_with(mock_message)
    assert len(message_queue) == 0


def test_gcn_stream_run(mocker, gcn_config_path, logger):
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

    gcn_stream = GCNStream(gcn_config_path, logger=logger, restart_queue=False)

    # Run the GCN stream
    gcn_stream.run(test=True)

    # Assertions
    assert mock_poll_method.call_count == 121  # Still unclear why it is called 3 times
    mock_commit_method.assert_called_once_with(mock_message)
    assert len(message_queue) == 0
