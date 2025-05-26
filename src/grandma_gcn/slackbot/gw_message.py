from typing import Any, Callable
from fink_utils.slack_bot.msg_builder import Message

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.gw_alert import GW_alert

from grandma_gcn.slackbot.element_extension import (
    BaseSection,
    MarkdownText,
    Text,
    RichTextElement,
    URLButton,
    Action,
)

from fink_utils.slack_bot.rich_text.rich_text_element import RichTextStyle
from fink_utils.slack_bot.rich_text.rich_section import SectionElement

from astropy.time import Time

from fink_utils.slack_bot.bot import post_msg_on_slack
from slack_sdk import WebClient


def instruments_to_markdown(instruments: list[GW_alert.Instrument]) -> str:
    """
    Convert a list of instruments into a Markdown bullet list.

    Parameters
    ----------
    instruments : list[GW_alert.Instrument]
        The list of instruments to convert.

    Returns
    -------
    str
        A Markdown-formatted bullet list of instruments.
    """
    if not instruments:
        return "No instruments available."

    return "\n".join(f"- {instrument.value}" for instrument in instruments)


def build_gwalert_msg(gw_alert: GW_alert) -> Message:
    """
    Build a message for the GW alert.
    Parameters
    ----------
    gw_alert : GW_alert
        The GW alert object.
    Returns
    -------
    Message
        The message object containing the alert information.
    """

    gw_alert.logger.info("Building message for GW alert")

    score, msg_fa, action = gw_alert.gw_score()

    msg = Message()

    alert_type = gw_alert.event_type

    msg.add_header("{} GW Alert: {}".format(alert_type.to_emoji(), gw_alert.event_id))
    msg.add_divider()

    time_since_t0 = Time.now() - gw_alert.get_event_time()
    delta_t0_formatted = format(time_since_t0.sec, "_.4f").replace("_", " ")

    _, region_size_90, mean_distance, mean_sigma = gw_alert.get_error_region(0.9)
    _, region_size_50, _, _ = gw_alert.get_error_region(0.5)

    msg.add_elements(
        BaseSection()
        .add_elements(
            MarkdownText("*Alert type:*\n{}".format(alert_type.value)),
        )
        .add_elements(
            MarkdownText(
                "*Event time:*\n{} UTC\n(Time since T0: {} seconds)".format(
                    gw_alert.get_event_time().iso, delta_t0_formatted
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "*Prefered class:*\n{} {}".format(
                    gw_alert.event_class.value, gw_alert.event_class.to_emoji()
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "*Instruments:*\n{}".format(
                    instruments_to_markdown(gw_alert.instruments)
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "*Credible region size:*\n- 90% = {:.2f} deg²\n- 50% = {:.2f} deg²".format(
                    region_size_90, region_size_50
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "*Mean luminosity distance:*\n{:.2f} ± {:.2f} Mpc".format(
                    mean_distance, mean_sigma
                )
            ),
        )
        .add_elements(
            MarkdownText("*GRANDMA Score:* {}".format(score)),
        )
        .add_elements(MarkdownText("*Message for FA:* \n{}".format(msg_fa)))
        .add_elements(MarkdownText("*Action to take:* {}".format(action.value))),
    )

    msg.add_elements(
        RichTextElement().add_elements(
            SectionElement().add_elements(
                Text("Useful links:", style=RichTextStyle.ITALIC).add_style(
                    RichTextStyle.BOLD
                ),
            )
        )
    )

    skyportal_button = URLButton(
        "SkyPortal - {}".format(gw_alert.event_id),
        "https://skyportal-icare.ijclab.in2p3.fr/source/{}".format(gw_alert.event_id),
        emoji=True,
    )

    grace_db_button = URLButton(
        "GraceDB - {}".format(gw_alert.event_id),
        gw_alert.gracedb_url,
        emoji=True,
    )

    url_owncloud_event = "https://grandma-owncloud.lal.in2p3.fr/index.php/apps/files/?dir=/candidates/gw/{}".format(
        gw_alert.event_id
    )

    owncloud_repo_button = URLButton(
        "OwnCloud - {}".format(gw_alert.event_id),
        url_owncloud_event,
        emoji=True,
    )

    owncloud_repo_image_button = URLButton(
        "OwnCloud - Image",
        url_owncloud_event + "/images",
        emoji=True,
    )

    owncloud_repo_photometry_button = URLButton(
        "OwnCloud - Photometry",
        url_owncloud_event + "/logbook",
        emoji=True,
    )

    msg.add_elements(
        Action()
        .add_elements(
            skyportal_button,
        )
        .add_elements(
            grace_db_button,
        )
        .add_elements(
            owncloud_repo_button,
        )
        .add_elements(
            owncloud_repo_image_button,
        )
        .add_elements(
            owncloud_repo_photometry_button,
        )
    )

    msg.add_divider()

    return msg


def build_gwemopt_message(
    gw_alert: GW_alert,
    obs_strategy: GW_alert.ObservationStrategy,
    celery_task_id: int,
    task_start_time: Time,
) -> Message:
    """
    Build a message for the new GWEMOPT processing task.

    Parameters
    ----------
    gw_alert : GW_alert
        The GW alert object.
    obs_strategy : GW_alert.ObservationStrategy
        The observation strategy used for the processing.
    celery_task_id : int
        The ID of the Celery task.
    task_start_time : Time
        The start time of the task.
    slack_client : WebClient
        The Slack client to use for sending the message.
    channel : str
        The Slack channel to send the message to.
    logger : LoggerNewLine
        The logger to use for logging messages.

    Returns
    -------
    Message
        The message object containing the task information.
    """

    gw_alert.logger.info("Building message for new GWEMOPT processing task")

    msg = Message()
    msg.add_header("New GWEMOPT processing for {}".format(gw_alert.event_id))
    msg.add_divider()
    msg.add_elements(
        BaseSection()
        .add_elements(
            MarkdownText("*Task ID:*\n{}".format(celery_task_id)),
        )
        .add_elements(
            MarkdownText("Task started at: {}".format(task_start_time.iso)),
        )
        .add_elements(
            MarkdownText("*Strategy :*\n{}".format(obs_strategy.value)),
        )
    )

    return msg


def new_alert_on_slack(
    gw_alert: GW_alert,
    build_msg_function: Callable[[GW_alert], Message],
    slack_client: WebClient,
    channel: str,
    logger: LoggerNewLine,
    **kwargs: dict[str, Any],
) -> None:
    """
    Send the alert to slack
    Parameters
    ----------
    gw_alert : GW_alert
        the alert to send
    slack_client : WebClient
        the slack client to use to send the message
    channel : str
        the channel to send the message to
    logger : LoggerNewLine
        the logger to use
    """

    msg = build_msg_function(gw_alert, **kwargs)

    post_msg_on_slack(
        slack_client,
        channel,
        [msg],
        logger=logger,
        verbose=False,
    )

    logger.info("Alert sent to Slack channel: {}".format(channel))
