import json
from collections.abc import Callable

from fink_utils.slack_bot.msg_builder import Message
from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.grb_alert import GRB_alert
from grandma_gcn.slackbot.element_extension import (
    BaseSection,
    MarkdownText,
)


def build_svom_alert_msg(grb_alert: GRB_alert, **kwargs) -> Message:
    """
    Build a Slack message for an SVOM GRB alert.

    Shows packet type (202=Initial, 204=Slewing, 205=Not slewing) and slew status.

    Parameters
    ----------
    grb_alert : GRB_alert
        The SVOM GRB alert object.
    **kwargs
        Additional keyword arguments (unused).

    Returns
    -------
    Message
        A formatted Slack message for the SVOM alert.
    """
    alert_data = grb_alert.to_slack_format()
    packet_type = alert_data["packet_type"]

    if packet_type == 202:
        type_label = "Eclairs wakeup"
    elif packet_type in [204, 205]:
        slew_status = alert_data.get("slew_status", "unknown")
        type_label = f"Slewing: {slew_status}"
    else:
        type_label = f"{packet_type}"

    message_text = (
        f"• *Packet type:* {type_label}\n"
        f"• *Trigger Time:* {alert_data['trigger_time']}\n"
        f"• *Position:* RA {alert_data['ra']}, DEC {alert_data['dec']}\n"
        f"• *Uncertainty:* {alert_data['uncertainty_arcmin']} arcmin\n"
        f":grb: <{alert_data['skyportal_link']}|SkyPortal Link>"
    )

    msg = Message()
    msg.add_header(f"🔔 New SVOM GRB: {alert_data['trigger_id']}")
    msg.add_divider()
    msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))

    return msg


def build_swift_alert_msg(grb_alert: GRB_alert, **kwargs) -> Message:
    """
    Build a Slack message for a GRB alert notification.

    For Swift alerts, if a BAT alert is provided, the message will combine
    information from both BAT and XRT alerts.

    Format (Swift BAT + XRT combined):
    :grb: Alert : Swift at [BAT Trigger Time]
    BAT Position: RA, DEC with UNC : [XX] arcmin
    XRT Position: RA, DEC with UNC : [XX] arcmin
    Skyportal Link

    Parameters
    ----------
    grb_alert : GRB_alert
        The GRB alert object (typically XRT for Swift).
    **kwargs
        Additional keyword arguments:
        - bat_alert: Optional GRB_alert object for BAT alert (for Swift combined messages)

    Returns
    -------
    Message
        A formatted Slack message for the GRB alert.
    """
    bat_alert = kwargs.get("bat_alert")
    xrt_alert = kwargs.get("xrt_alert")

    # Get common data from first available alert
    first = bat_alert or xrt_alert or grb_alert
    data = first.to_slack_format()

    # Build position lines for each available alert
    positions = {"BAT": bat_alert, "XRT": xrt_alert}
    pos_lines = [
        f"• *{name} Position:* RA {alert.to_slack_format()['ra']}, "
        f"DEC {alert.to_slack_format()['dec']} "
        f"(UNC: {alert.to_slack_format()['uncertainty_arcmin']} arcmin)"
        for name, alert in positions.items()
        if alert
    ]

    message_text = (
        f"• *Trigger Time:* {data['trigger_time']}\n"
        f"{chr(10).join(pos_lines)}\n"
        f":grb: <{data['skyportal_link']}|SkyPortal Link>"
    )

    msg = Message()
    msg.add_header(f"🔔 New Swift GRB: {data['trigger_id']}")
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
