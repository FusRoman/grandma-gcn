"""Tests for GRB Slack message builders."""

from grandma_gcn.gcn_stream.grb_alert import GRB_alert
from grandma_gcn.slackbot.grb_message import (
    build_svom_alert_msg,
    build_swift_alert_msg,
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


def test_build_svom_alert_msg_basic(svom_eclairs_alert: GRB_alert):
    """Test basic SVOM alert message building."""
    msg = build_svom_alert_msg(grb_alert=svom_eclairs_alert)

    assert msg is not None
    assert msg.blocks is not None
    blocks_str = str(msg.blocks)
    assert "SVOM" in blocks_str or "GRB" in blocks_str


def test_build_svom_alert_msg_thread_update(svom_eclairs_alert: GRB_alert):
    """Test SVOM thread update message."""
    msg = build_svom_alert_msg(
        grb_alert=svom_eclairs_alert,
        is_thread_update=True,
    )

    assert msg is not None


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
