import json
from pathlib import Path
from pytest import mark

from tests.test_gw_alert import open_notice_file


@mark.e2e
def test_e2e_grandma(mocker, logger):
    from grandma_gcn.gcn_stream.stream import GCNStream

    # Simulate a message queue
    message_queue = []

    # Create a mocked message
    mock_message = mocker.Mock()
    mock_message.topic.return_value = "igwn.gwalert"
    mock_message.offset.return_value = 42
    mock_message.error.return_value = None
    mock_message.value.return_value = open_notice_file(
        Path("tests"), "S250207bg-preliminary.json"
    )

    # Add the mocked message to the queue
    message_queue.append(mock_message)

    # Create a second mocked message
    mock_message = mocker.Mock()
    mock_message.topic.return_value = "igwn.gwalert"
    mock_message.offset.return_value = 42
    mock_message.error.return_value = None
    mock_message.value.return_value = open_notice_file(
        Path("tests"), "S241102br-preliminary.json"
    )

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
    assert len(saved_files) == 2
    with open(saved_files[0], "r") as f:
        saved_notice = json.load(f)
    assert saved_notice["superevent_id"] == "S250207bg"  # Example assertion
