"""Tests for GRB Slack message builders."""

from unittest.mock import MagicMock

import pytest

from grandma_gcn.gcn_stream.grb_alert import GRB_alert
from grandma_gcn.slackbot.grb_message import (
    build_svom_alert_msg,
    build_swift_alert_msg,
    send_grb_alert_to_slack,
)


def test_build_swift_alert_msg_basic(swift_bat_alert: GRB_alert):
    """Test basic Swift alert message building."""
    msg = build_swift_alert_msg(grb_alert=swift_bat_alert, bat_alert=swift_bat_alert)

    assert msg is not None
    assert msg.blocks is not None
    blocks_str = str(msg.blocks)
    assert "Swift" in blocks_str or "GRB" in blocks_str


def test_build_swift_alert_msg_with_xrt(
    swift_bat_alert: GRB_alert, swift_uvot_alert: GRB_alert
):
    """Test Swift alert message with XRT position."""
    msg = build_swift_alert_msg(
        grb_alert=swift_bat_alert,
        bat_alert=swift_bat_alert,
        xrt_alert=swift_bat_alert,
        is_xrt_update=False,
    )

    assert msg is not None
    assert msg.blocks is not None


def test_build_swift_alert_msg_xrt_update(swift_bat_alert: GRB_alert):
    """Test Swift XRT position update message."""
    msg = build_swift_alert_msg(
        grb_alert=swift_bat_alert,
        bat_alert=swift_bat_alert,
        xrt_alert=swift_bat_alert,
        is_xrt_update=True,
    )

    assert msg is not None
    blocks_str = str(msg.blocks)
    assert "Update" in blocks_str or "XRT" in blocks_str or "Position" in blocks_str


def test_build_swift_alert_msg_uvot_update(
    swift_bat_alert: GRB_alert, swift_uvot_alert: GRB_alert
):
    """Test Swift UVOT position update message."""
    msg = build_swift_alert_msg(
        grb_alert=swift_uvot_alert,
        bat_alert=swift_bat_alert,
        uvot_alert=swift_uvot_alert,
        is_uvot_update=True,
    )

    assert msg is not None


def test_build_swift_alert_msg_with_skyportal_link(swift_bat_alert: GRB_alert):
    """Test Swift alert message includes SkyPortal link when provided."""
    skyportal_link = "https://skyportal.io/source/GCN-260204_1448"
    msg = build_swift_alert_msg(
        grb_alert=swift_bat_alert,
        bat_alert=swift_bat_alert,
        skyportal_link=skyportal_link,
    )

    assert msg is not None
    assert "skyportal.io" in str(msg.blocks)


def test_build_svom_alert_msg_basic(svom_eclairs_alert: GRB_alert):
    """Test basic SVOM alert message building."""
    msg = build_svom_alert_msg(grb_alert=svom_eclairs_alert)

    assert msg is not None
    assert msg.blocks is not None
    blocks_str = str(msg.blocks)
    assert "SVOM" in blocks_str or "GRB" in blocks_str


def test_build_svom_alert_msg_with_skyportal_link(svom_eclairs_alert: GRB_alert):
    """Test SVOM alert message includes SkyPortal link when provided."""
    skyportal_link = "https://skyportal.io/source/GCN-260208_1700"
    msg = build_svom_alert_msg(
        grb_alert=svom_eclairs_alert,
        skyportal_link=skyportal_link,
    )

    assert msg is not None
    assert "skyportal.io" in str(msg.blocks)


def test_build_svom_alert_msg_thread_update(svom_eclairs_alert: GRB_alert):
    """Test SVOM thread update message (packet 202 falls through to initial alert)."""
    msg = build_svom_alert_msg(
        grb_alert=svom_eclairs_alert,
        is_thread_update=True,
    )

    assert msg is not None


def test_build_svom_alert_msg_thread_update_slew_packet(
    svom_eclairs_alert: GRB_alert, mocker
):
    """Test SVOM thread update message with slew packet type (204/205)."""
    mocker.patch(
        "grandma_gcn.gcn_stream.grb_alert.vp.get_toplevel_params",
        return_value={"Packet_Type": {"value": "204"}},
    )
    msg = build_svom_alert_msg(
        grb_alert=svom_eclairs_alert,
        is_thread_update=True,
    )

    assert msg is not None
    assert "Slew" in str(msg.blocks)


def test_build_svom_alert_msg_mxt_update(
    svom_eclairs_alert: GRB_alert, svom_mxt_alert: GRB_alert
):
    """Test SVOM MXT position update message."""
    msg = build_svom_alert_msg(
        grb_alert=svom_mxt_alert,
        mxt_alert=svom_mxt_alert,
        is_mxt_update=True,
    )

    assert msg is not None


def test_send_grb_alert_to_slack(svom_eclairs_alert: GRB_alert, logger):
    """Test that send_grb_alert_to_slack calls the Slack API and returns the response."""
    slack_client = MagicMock()
    slack_client.chat_postMessage.return_value = {"ts": "12345"}

    response = send_grb_alert_to_slack(
        grb_alert=svom_eclairs_alert,
        message_builder=build_svom_alert_msg,
        slack_client=slack_client,
        channel="#test-grb",
        logger=logger,
    )

    assert slack_client.chat_postMessage.called
    assert response == {"ts": "12345"}


def test_send_grb_alert_to_slack_with_thread_ts(svom_eclairs_alert: GRB_alert, logger):
    """Test that thread_ts is forwarded to the Slack API call."""
    slack_client = MagicMock()

    send_grb_alert_to_slack(
        grb_alert=svom_eclairs_alert,
        message_builder=build_svom_alert_msg,
        slack_client=slack_client,
        channel="#test-grb",
        logger=logger,
        thread_ts="1234567890.123456",
    )

    call_kwargs = slack_client.chat_postMessage.call_args[1]
    assert call_kwargs["thread_ts"] == "1234567890.123456"


def test_send_grb_alert_to_slack_failure(svom_eclairs_alert: GRB_alert, logger):
    """Test that send_grb_alert_to_slack re-raises Slack API errors."""
    slack_client = MagicMock()
    slack_client.chat_postMessage.side_effect = Exception("Slack API error")

    with pytest.raises(Exception, match="Slack API error"):
        send_grb_alert_to_slack(
            grb_alert=svom_eclairs_alert,
            message_builder=build_svom_alert_msg,
            slack_client=slack_client,
            channel="#test-grb",
            logger=logger,
        )
