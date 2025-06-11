import json
from pathlib import Path
from pytest import mark

from tests.conftest import open_notice_file

import time


def push_message_for_test(mocker, message_queue: list, topic: str, notice_file: str):
    """
    Helper function to push a message to the mocked Kafka consumer for testing.
    """
    mock_message = mocker.Mock()
    mock_message.topic.return_value = topic
    mock_message.offset.return_value = len(message_queue) + 1
    mock_message.error.return_value = None
    mock_message.value.return_value = open_notice_file(Path("tests"), notice_file)

    message_queue.append(mock_message)

    return mock_message


@mark.e2e
def test_e2e_grandma(mocker, logger):
    """
    End-to-end test for the GCNStream class in the grandma_gcn package.
    This test simulates the processing of GCN notices from a Kafka topic,
    ensuring that notices are correctly consumed, processed and then
    removed from the disk by a celery post processing task.

    It uses mocked messages to simulate the Kafka consumer behavior and
    verifies that the notices are saved to a specified directory.

    To run the e2e test, you need a the grandma-gcn configuration file
    in toml format with the good secret in it, including
    the kafka GCN id and secret, the slackbot token, the slack channel id where to send
    the gwemopt plot as well as the owncloud username and password.

    The owncloud url should be the WebDAV url of the owncloud instance.
    """
    from grandma_gcn.gcn_stream.stream import GCNStream

    # Simulate a message queue
    message_queue = []

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-preliminary.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-initial.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S250207bg-preliminary.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-update.json"
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
        # Simulate a delay for processing
        time.sleep(60)

    mock_commit_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.commit", side_effect=mock_commit
    )

    shared_path = Path("/shared-tmp")

    path_e2e_config = Path("gcn_stream_config.toml")
    # Mock the GCNStream.notice_path attribute to use the temporary directory
    gcn_stream = GCNStream(path_e2e_config, logger=logger, restart_queue=False)
    mocker.patch.object(gcn_stream, "notice_path", shared_path)

    # Run the GCN stream
    gcn_stream.run(test=True)

    # Assertions
    assert mock_poll_method.call_count == 121
    assert mock_commit_method.call_count == 2
    assert len(message_queue) == 0

    # Verify that the notices were saved to the temporary directory
    saved_files = list(shared_path.glob("*.json"))
    saved_files.sort()
    assert len(saved_files) == 2
    with open(saved_files[0], "r") as f:
        saved_notice = json.load(f)
    assert saved_notice["superevent_id"] == "S241102br"  # Example assertion
