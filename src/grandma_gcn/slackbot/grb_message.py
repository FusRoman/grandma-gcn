import json
from collections.abc import Callable

from fink_utils.slack_bot.msg_builder import Message
from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.grb_alert import GRB_alert
from grandma_gcn.slackbot.element_extension import BaseSection, MarkdownText


def _build_position_update_message(
    grb_name: str,
    position_type: str,
    ra: str,
    dec: str,
    uncertainty: str | None = None,
    magnitude: str | None = None,
) -> Message:
    """
    Helper function to build a position update message.

    Parameters
    ----------
    grb_name : str
        The GRB name
    position_type : str
        Type of position update (e.g., "XRT Position updated", "MXT Position", "Optical counterpart found by Swift/UVOT")
    ra : str
        Right Ascension
    dec : str
        Declination
    uncertainty : str | None
        Uncertainty in arcmin (optional, not shown if None)
    magnitude : str | None
        Burst magnitude (optional, for UVOT updates)

    Returns
    -------
    Message
        A formatted Slack message for the position update
    """
    msg = Message()

    # Build message text
    if uncertainty:
        message_text = (
            f"• *{position_type}:* RA {ra}, DEC {dec} (UNC: {uncertainty} arcmin)"
        )
    elif magnitude:
        message_text = f"• *{position_type}*\n• *Position:* RA {ra}, DEC {dec}\n• *Magnitude:* {magnitude}"
    else:
        message_text = f"• *{position_type}*\n• *Position:* RA {ra}, DEC {dec}"

    msg.add_header(
        f"Update: {'Swift' if 'Swift' in position_type or 'XRT' in position_type or 'UVOT' in position_type else 'SVOM'} GRB {grb_name}"
    )
    msg.add_divider()
    msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))

    return msg


def build_svom_alert_msg(grb_alert: GRB_alert, **kwargs) -> Message:
    """
    Build a Slack message for an SVOM GRB alert.

    For initial alert (packet 202): Shows full details with trigger info
    For slew updates (packets 204, 205): Shows only slew status change
    For MXT updates (packet 209): Shows MXT position

    Parameters
    ----------
    grb_alert : GRB_alert
        The SVOM GRB alert object.
    **kwargs
        Additional keyword arguments:
        - is_thread_update: Boolean indicating if this is a thread update (for slew status)
        - mxt_alert: GRB_alert object for MXT alert (provides position)
        - is_mxt_update: Boolean indicating if this is an MXT position update

    Returns
    -------
    Message
        A formatted Slack message for the SVOM alert.
    """
    packet_type = grb_alert.packet_type
    is_thread_update = kwargs.get("is_thread_update", False)
    mxt_alert = kwargs.get("mxt_alert")
    is_mxt_update = kwargs.get("is_mxt_update", False)

    msg = Message()

    # For MXT position updates, show MXT position
    if is_mxt_update and mxt_alert:
        return _build_position_update_message(
            grb_alert.grb_name,
            "MXT Position",
            f"{mxt_alert.ra:.2f}",
            f"{mxt_alert.dec:.2f}",
        )

    # For thread updates (slew status changes), only show the status
    if is_thread_update and packet_type in [204, 205]:
        slew_status = getattr(grb_alert, "slew_status", "unknown")
        message_text = f"• *Slew Status:* {slew_status}"
        msg.add_header(f"Update: SVOM GRB {grb_alert.grb_name}")
        msg.add_divider()
        msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))
        return msg

    # For initial alert (packet 202) or first message
    message_text = (
        f"• *Trigger Time:* {grb_alert.trigger_time_formatted}\n"
        f"• *Rate_Signif:* {grb_alert.rate_signif} / *Image_Signif:* {grb_alert.image_signif} / *Trigger_Dur:* {grb_alert.trigger_dur}\n"
        f"• *Position:* RA {grb_alert.ra:.2f}, DEC {grb_alert.dec:.2f}\n"
        f"• *Uncertainty:* {grb_alert.ra_dec_error_arcmin:.2f} arcmin\n"
        f":grb: <{grb_alert.skyportal_link}|SkyPortal Link>"
    )

    msg.add_header(f"🔔 New SVOM GRB {grb_alert.grb_name} / {grb_alert.trigger_id}")
    msg.add_divider()
    msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))

    return msg


def build_swift_alert_msg(grb_alert: GRB_alert, **kwargs) -> Message:
    """
    Build a Slack message for a Swift GRB alert.

    For initial alert: Shows GRB name, trigger info from BAT, and XRT position
    For XRT updates: Shows only updated XRT position in simplified format
    For UVOT updates: Shows optical counterpart position without uncertainty

    Parameters
    ----------
    grb_alert : GRB_alert
        The GRB alert object.
    **kwargs
        Additional keyword arguments:
        - bat_alert: GRB_alert object for BAT alert (provides trigger info)
        - xrt_alert: GRB_alert object for XRT alert (provides position)
        - uvot_alert: GRB_alert object for UVOT alert (provides optical position)
        - is_xrt_update: Boolean indicating if this is an XRT position update
        - is_uvot_update: Boolean indicating if this is a UVOT position update

    Returns
    -------
    Message
        A formatted Slack message for the Swift alert.
    """
    bat_alert = kwargs.get("bat_alert")
    xrt_alert = kwargs.get("xrt_alert")
    uvot_alert = kwargs.get("uvot_alert")
    is_xrt_update = kwargs.get("is_xrt_update", False)
    is_uvot_update = kwargs.get("is_uvot_update", False)

    # Get GRB name and trigger ID from BAT, XRT, or UVOT
    first = bat_alert or xrt_alert or uvot_alert or grb_alert

    msg = Message()

    # For UVOT position updates, show optical counterpart message with magnitude
    if is_uvot_update and uvot_alert:
        return _build_position_update_message(
            first.grb_name,
            "Optical counterpart found by Swift/UVOT",
            f"{uvot_alert.ra:.2f}",
            f"{uvot_alert.dec:.2f}",
            magnitude=f"{uvot_alert.burst_mag:.2f}",
        )

    if is_xrt_update and xrt_alert:
        return _build_position_update_message(
            first.grb_name,
            "XRT Position updated",
            f"{xrt_alert.ra:.2f}",
            f"{xrt_alert.dec:.2f}",
            f"{xrt_alert.ra_dec_error_arcmin:.2f}",
        )

    message_text_parts = [f"• *Trigger Time:* {first.trigger_time_formatted}"]

    # Add trigger info (Rate_Signif, Image_Signif, Trigger_Dur) from BAT if available
    if bat_alert:
        trigger_info = (
            f"• *Trigger info:* Rate_Signif: {bat_alert.rate_signif} / "
            f"Image_Signif: {bat_alert.image_signif} / "
            f"Trigger_Dur: {bat_alert.trigger_dur}"
        )
        message_text_parts.append(trigger_info)

    # Add XRT position only
    if xrt_alert:
        xrt_position = (
            f"• *XRT Position:* RA {xrt_alert.ra:.2f}, DEC {xrt_alert.dec:.2f} "
            f"(UNC: {xrt_alert.ra_dec_error_arcmin:.2f} arcmin)"
        )
        message_text_parts.append(xrt_position)

    message_text_parts.append(f":grb: <{first.skyportal_link}|SkyPortal Link>")
    message_text = "\n".join(message_text_parts)

    msg.add_header(
        f"🔔 New Swift GRB {first.grb_name} / Trigger ID: {first.trigger_id}"
    )
    msg.add_divider()
    msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))

    return msg


def send_grb_alert_to_slack(
    grb_alert: GRB_alert,
    message_builder: Callable,
    slack_client: WebClient,
    channel: str,
    logger: LoggerNewLine,
    thread_ts: str | None = None,
    **kwargs,
) -> SlackResponse:
    """
    Send a GRB alert message to Slack.

    Parameters
    ----------
    grb_alert : GRB_alert
        The GRB alert object.
    message_builder : Callable
        Function to build the Slack message (e.g., build_grb_alert_msg).
    slack_client : WebClient
        The Slack WebClient instance.
    channel : str
        The Slack channel to post to (e.g., "#grb-alerts").
    logger : LoggerNewLine
        Logger instance for logging.
    **kwargs
        Additional keyword arguments passed to the message builder.

    Returns
    -------
    SlackResponse
        The Slack API response.
    """
    msg = message_builder(grb_alert, **kwargs)

    try:
        fallback_text = f"{grb_alert.mission.value} GRB: {grb_alert.trigger_id}"
        blocks_json = json.dumps(msg.blocks["blocks"])

        response = slack_client.chat_postMessage(
            channel=channel,
            text=fallback_text,
            blocks=blocks_json,
            thread_ts=thread_ts,
        )

        logger.info(
            f"GRB alert sent to Slack channel {channel}: {grb_alert.trigger_id}"
        )
        return response

    except Exception as e:
        logger.error(f"Failed to send GRB alert to Slack: {e}")
        raise
