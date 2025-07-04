"""
End-to-End (E2E) test suite.

WARNING:
These tests are marked with `@mark.e2e` or `@mark.e2e_light` to bypass
certain global fixtures, specifically `set_fake_slack_token` in the conftest file, which is applied by default
to all tests via `autouse=True`.

This allows E2E tests to run in a real or controlled integration environment without mocking Slack.

    If your test needs to **bypass mocking**, ensure it is marked accordingly:
        @mark.e2e
        def test_my_integration(): ...
"""

from dotenv import dotenv_values
from numpy.random import random
import json
from pathlib import Path
from pytest import mark
from unittest.mock import patch, MagicMock
from astropy.table import Table

from grandma_gcn.database.init_db import init_db
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

    GWEMOPT is automatically triggered during this test so the execution can be slow.
    See the test_e2e_light for a faster version of this test where GWEMOPT is mocked.

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

    # initialize the sql database connection
    config = dotenv_values(".env")  # Load environment variables from .env file
    DATABASE_URL = config["SQLALCHEMY_DATABASE_URI"]
    engine, session_local = init_db(DATABASE_URL, logger=logger, echo=True)

    with session_local() as session:
        # Mock the GCNStream.notice_path attribute to use the temporary directory
        gcn_stream = GCNStream(
            path_e2e_config, engine, session, logger=logger, restart_queue=False
        )
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


@mark.e2e_light
def test_e2e_grandma_light(mocker, logger, tiles: dict[str, Table]):
    """
    End-to-end test for the GCNStream class in the grandma_gcn package.
    This test simulates the processing of GCN notices from a Kafka topic,
    ensuring that notices are correctly consumed, processed and then
    removed from the disk by a celery post processing task.

    This test is faster than the test_e2e_grandma as it mocks the GWEMOPT process.
    """
    from grandma_gcn.gcn_stream.stream import GCNStream
    from grandma_gcn.worker.celery_app import celery
    from grandma_gcn.slackbot.gw_message import (
        post_image_on_slack as real_post_image_on_slack,
    )

    celery.conf.update(task_always_eager=True)

    # Simulate a message queue
    message_queue = []

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-preliminary.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "gw_notice_significant.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S241102br-initial.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "S250207bg-preliminary.json"
    )

    push_message_for_test(
        mocker, message_queue, "igwn.gwalert", "gw_notice_unsignificant.json"
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

    mock_commit_method = mocker.patch(
        "grandma_gcn.gcn_stream.consumer.KafkaConsumer.commit", side_effect=mock_commit
    )

    shared_path = Path("/shared-tmp")

    path_e2e_config = Path("gcn_stream_config.toml")

    # initialize the sql database connection
    config = dotenv_values(".env")  # Load environment variables from .env file
    DATABASE_URL = config["SQLALCHEMY_DATABASE_URI"]
    engine, session_local = init_db(DATABASE_URL, logger=logger, echo=True)

    with session_local() as session:
        # Mock the GCNStream.notice_path attribute to use the temporary directory
        gcn_stream = GCNStream(
            path_e2e_config, engine, session, logger=logger, restart_queue=False
        )
        mocker.patch.object(gcn_stream, "notice_path", shared_path)

        # mock the Observation_plan_multiple of the gwemopt package to speed up the test
        with (
            patch(
                "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
            ) as mock_obs_plan,
            patch(
                "grandma_gcn.gcn_stream.gw_alert.GW_alert.integrated_surface_percentage",
                return_value=random() * 100,
            ) as _,
        ):
            mock_obs_plan.return_value = (tiles, MagicMock())
            with patch(
                "grandma_gcn.worker.gwemopt_worker.open", create=True
            ) as mock_ascii_open:

                # We mock only the "w" mode for ascii_open
                # to simulate writing the ascii tiles file.
                # For other modes, we use the real open function.
                def open_side_effect(file, mode="r", *args, **kwargs):
                    if mode == "w":
                        mock_file = MagicMock()
                        mock_file.__enter__.return_value = MagicMock()
                        return mock_file
                    else:
                        # For other modes, use the real open
                        from builtins import open as real_open

                        return real_open(file, mode, *args, **kwargs)

                mock_ascii_open.side_effect = open_side_effect

                custom_filepath = Path("tests/data/coverage_S241102br_Tiling_map.png")

                def patched_post_image_on_slack(
                    slack_client,
                    filepath,
                    filename,
                    filetitle,
                    channel_id,
                    alt_text=None,
                    threads_ts=None,
                ):
                    return real_post_image_on_slack(
                        slack_client=slack_client,
                        filepath=custom_filepath,
                        filename=filename,
                        filetitle=filetitle,
                        channel_id=channel_id,
                        alt_text=alt_text,
                        threads_ts=threads_ts,
                    )

                with patch(
                    "grandma_gcn.worker.gwemopt_worker.post_image_on_slack",
                    side_effect=patched_post_image_on_slack,
                ) as _:
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
