import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from astropy.table import Table
from astropy.time import Time
from fink_utils.slack_bot.msg_builder import Message
from fink_utils.slack_bot.rich_text.rich_section import SectionElement
from fink_utils.slack_bot.rich_text.rich_text_element import RichTextStyle
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.element_extension import (
    Action,
    BaseSection,
    MarkdownText,
    PlainText,
    RichTextElement,
    Text,
    URLButton,
)


def get_grandma_owncloud_public_url() -> str:
    """
    Get the GRANDMA OwnCloud URL.
    This URL is used to access the GRANDMA OwnCloud instance.
    This is not the WebDAV URL, but the public URL to access the files.
    A grandma authentication is still required to access the folders and files

    Returns
    -------
    str
        The GRANDMA OwnCloud URL.
    """
    return "https://grandma-owncloud.lal.in2p3.fr/index.php/apps/files/?dir=/"


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


def build_gwalert_notification_msg(gw_alert: GW_alert) -> Message:
    """
    Build a minimal Slack message to notify of a new GW alert with unknown significance.

    Parameters
    ----------
    gw_alert : GW_alert
        The GW alert object.

    Returns
    -------
    Message
        A minimal notification message.
    """

    indent = "\u00a0" * 8
    message_content = (
        f"{indent}⏳ Pending validation by the shifter team…\n"
        f"{indent*2}Check thread messages for more details !"
    )

    msg = Message()
    msg.add_header(f"🔔 New GW alert received: {gw_alert.event_id}")
    msg.add_divider()
    msg.add_elements(
        BaseSection().add_text(
            # The \u00a0 is a non-breaking space, used to indent the text
            PlainText(
                message_content,
                emoji=True,
            )
        )
    )

    return msg


def build_gwalert_data_msg(
    gw_alert: GW_alert, path_gw_alert: str, nb_alert_received: int
) -> Message:
    """
    Build a message for the GW alert.

    Parameters
    ----------
    gw_alert : GW_alert
        The GW alert object.
    path_gw_alert : str
        The path to the alert folder on OwnCloud.
    nb_alert_received : int
        The number of alerts received so far.

    Returns
    -------
    Message
        The message object containing the alert information.
    """

    gw_alert.logger.info("Building message for GW alert")

    score, _, action = gw_alert.gw_score()

    msg = Message()

    alert_type = gw_alert.event_type

    msg.add_header(
        "{} Alert N°{} - {}".format(
            alert_type.to_emoji(), nb_alert_received, alert_type.value
        )
    )
    msg.add_divider()

    time_since_t0 = Time.now() - gw_alert.get_event_time()
    delta_t0_formatted = format(time_since_t0.sec, "_.4f").replace("_", " ")

    _, region_size_90, mean_distance, mean_sigma = gw_alert.get_error_region(0.9)
    _, region_size_50, _, _ = gw_alert.get_error_region(0.5)

    main_section = BaseSection().add_elements(
        MarkdownText(
            "*Event time:*\n{} UTC\n(Time since T0: {} seconds)".format(
                gw_alert.get_event_time().iso, delta_t0_formatted
            )
        ),
    )

    class_event = gw_alert.event_class

    if class_event is None:
        main_section = main_section.add_elements(
            MarkdownText(
                "*Event class:*\nNo classification available",
            )
        )
    else:
        # Get the other classes and their probabilities
        # Exclude the class_event from the list of other classes
        others_class = [e for e in GW_alert.CBC_proba if e != class_event]
        other_class_msg = "\n".join(
            f"- {cbc_class.value} ({gw_alert.class_proba(cbc_class) * 100: .0f} %)"
            for cbc_class in others_class
        )
        main_section = main_section.add_elements(
            MarkdownText(
                "*Preferred class:*\n{}({:.0f} %) {}".format(
                    class_event.value,
                    gw_alert.class_proba(class_event) * 100,
                    class_event.to_emoji(),
                )
            ),
        ).add_elements(
            MarkdownText(f"*Other classes:*\n{other_class_msg}"),
        )

    main_section.add_elements(
        MarkdownText(
            f"*Instruments:*\n{instruments_to_markdown(gw_alert.instruments)}"
        ),
    ).add_elements(
        MarkdownText(
            "*Credible region size:*\n- 90% = {:.0f} deg²\n- 50% = {:.0f} deg²".format(
                region_size_90, region_size_50
            )
        ),
    ).add_elements(
        MarkdownText(
            "*Mean luminosity distance:*\n{:.0f} ± {:.0f} Mpc".format(
                mean_distance, mean_sigma
            )
        ),
    ).add_elements(
        MarkdownText(f"*GRANDMA Score:* {score}"),
    ).add_elements(
        MarkdownText(f"*Decision time:* {action.value}")
    )

    msg.add_elements(main_section)

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
        f"SkyPortal - {gw_alert.event_id}",
        f"https://skyportal-icare.ijclab.in2p3.fr/source/{gw_alert.event_id}",
        emoji=True,
    )

    grace_db_button = URLButton(
        f"GraceDB - {gw_alert.event_id}",
        gw_alert.gracedb_url,
        emoji=True,
    )

    # Public URL (meaning not the WebDAV url used to make the requests) for the OwnCloud event folder
    url_owncloud_event = get_grandma_owncloud_public_url() + path_gw_alert

    owncloud_repo_button = URLButton(
        f"OwnCloud - {gw_alert.event_id}",
        str(url_owncloud_event),
        emoji=True,
    )

    owncloud_repo_image_button = URLButton(
        "OwnCloud - Image",
        str(url_owncloud_event + "/IMAGES"),
        emoji=True,
    )

    owncloud_repo_photometry_button = URLButton(
        "OwnCloud - Photometry",
        str(url_owncloud_event + "/LOGBOOK"),
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
    telescopes: list[str],
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
    telescopes : list[str]
        List of telescopes involved in the gwemopt task.


    Returns
    -------
    Message
        The message object containing the task information.
    """

    gw_alert.logger.info("Building message for new GWEMOPT processing task")

    msg = Message()
    msg.add_header(f"🧠 New GWEMOPT processing for {gw_alert.event_id}")
    msg.add_divider()
    msg.add_elements(
        BaseSection()
        .add_elements(
            MarkdownText(f"🆔 *Task ID:*\n{celery_task_id}"),
        )
        .add_elements(
            MarkdownText(f"⏱️ Task started at: {task_start_time.iso}"),
        )
        .add_elements(
            MarkdownText(
                "*Strategy :*\n{} {}".format(
                    obs_strategy.to_emoji(), obs_strategy.value
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "🔭 *Telescopes:*\n{}".format(
                    "\n".join(f"- {tel}" for tel in telescopes)
                )
            ),
        )
    )
    msg.add_divider()

    return msg


def post_image_on_slack(
    slack_client: WebClient,
    filepath: Path,
    filename: str,
    filetitle: str,
    channel_id: str,
    alt_text: str | None = None,
    threads_ts: str | None = None,
) -> str:
    """
    Post an image file to a Slack channel.

    Parameters
    ----------
    slack_client : WebClient
        The Slack client to use for posting the image.
    filepath : Path
        The path to the image file to be uploaded.
    filename : str
        The name of the file as it will appear in Slack.
    filetitle : str
        The title of the file as it will appear in Slack.
    channel_id : str
        The ID of the Slack channel where the image will be posted.
        It is not the channel name, but the unique identifier for the channel.
    alt_text : str | None, optional
        Alternative text for the image, by default None.

    Returns
    -------
    str
        The public permalink to the uploaded image file in Slack.
    """
    with open(
        filepath,
        "rb",
    ) as file:
        upload_response = slack_client.files_upload_v2(
            file=file,
            filename=filename,
            title=filetitle,
            alt_text=alt_text,
            channel=channel_id,
            thread_ts=threads_ts,
        )

    file_info = upload_response["file"]
    return file_info["permalink_public"]


def build_gwemopt_results_message(
    gw_alert: GW_alert,
    tiles_plan: dict[str, Table | None],
    celery_task_id: int,
    obs_strategy: GW_alert.ObservationStrategy,
    telescopes: list[str],
    execution_time: float,
    path_gw_alert: str,
) -> Message:
    """
    Build a message for the GWEMOPT processing results.

    Parameters
    ----------
    gw_alert : GW_alert
        The GW alert object.
    tiles_plan : dict[str, Table]
        A dictionary mapping telescope names to their respective tiles plan.
    celery_task_id : int
        The ID of the Celery task that processed the alert.
    obs_strategy : GW_alert.ObservationStrategy
        The observation strategy used for the processing.
    telescopes : list[str]
        List of telescopes involved in the gwemopt task.
    execution_time : float
        The total execution time of the processing task in seconds.
    path_gwemopt_results : str
        The path to the gwemopt results folder on OwnCloud.

    Returns
    -------
    Message
        The message object containing the results of the GWEMOPT processing.
    """
    msg = Message()
    msg.add_header(f"🗺️ GWEMOPT processing finished for {gw_alert.event_id}")
    msg.add_divider()

    msg.add_elements(
        BaseSection()
        .add_elements(
            MarkdownText(f"*Task ID:*\n{celery_task_id}"),
        )
        .add_elements(
            MarkdownText(f"Total execution time: {execution_time:.3f}"),
        )
        .add_elements(
            MarkdownText(
                "*Strategy :*\n {} {}".format(
                    obs_strategy.to_emoji(), obs_strategy.value
                )
            ),
        )
        .add_elements(
            MarkdownText(
                "*Telescopes: (coverage percentage)*\n{}".format(
                    "\n".join(
                        f"- {tel} ({gw_alert.integrated_surface_percentage(tiles_plan[tel]):.0f} %)"
                        for tel in telescopes
                    )
                )
            ),
        )
    )

    # Public URL (meaning not the WebDAV url used to make the requests) for the OwnCloud event folder
    url_owncloud_gwemopt_results = get_grandma_owncloud_public_url() + path_gw_alert
    owncloud_repo_button = URLButton(
        f"OwnCloud - {gw_alert.event_id}",
        str(url_owncloud_gwemopt_results),
        emoji=True,
    )
    msg.add_elements(
        Action().add_elements(
            owncloud_repo_button,
        )
    )

    return msg


def post_msg_on_slack(
    webclient: WebClient,
    channel: str,
    msg: list[Message],
    thread_ts: str | None = None,
    logger: LoggerNewLine = None,
    verbose: bool = False,
) -> SlackResponse:
    """
    Send a msg on the specified slack channel

    Parameters
    ----------
    webclient : WebClient
        slack bot client
    channel : str
        the channel where will be posted the message
    msg : list
        list of message to post on slack, each string in the list will be a single post.
    thread_ts : str, optional
        if specified, the message will be posted in a thread, by default None
    sleep_delay : int, optional
        delay to wait between the message, by default 1
    logger : _type_, optional
        logger used to print logs, by default None
    verbose : bool, optional
        if true, print logs between the message, by default False

    * Notes:

    Before sending message on slack, check that the Fink bot have been added to the targeted channel.

    Examples
    --------
    see bot_test.py
    """
    try:
        for tmp_msg in msg:
            json_p = json.dumps(tmp_msg.blocks["blocks"])
            slack_message_response = webclient.chat_postMessage(
                channel=channel, text="msg blocks", blocks=json_p, thread_ts=thread_ts
            )

            if verbose:
                logger.debug("Post msg on slack successful")

            return slack_message_response
    except SlackApiError as e:
        if e.response["ok"] is False:
            logger.error("Post slack msg error", exc_info=1)


def new_alert_on_slack(
    gw_alert: GW_alert,
    build_msg_function: Callable[[GW_alert], Message],
    slack_client: WebClient,
    channel: str,
    logger: LoggerNewLine,
    thread_ts: str | None = None,
    **kwargs: dict[str, Any],
) -> SlackResponse:
    """
    Send the alert to slack

    Parameters
    ----------
    gw_alert : GW_alert
        the alert to send
    build_msg_function : Callable[[GW_alert], Message]
        a function that takes a GW_alert object and returns a Message object
    slack_client : WebClient
        the slack client to use to send the message
    channel : str
        the channel to send the message to
    logger : LoggerNewLine
        the logger to use
    thread_ts : str | None, optional
        if specified, the message will be posted in a thread, by default None
    **kwargs : dict[str, Any]
        additional keyword arguments to pass to the build_msg_function, such as:
        - celery_task_id: int
            The ID of the Celery task that processed the alert.
        - execution_time: float
            The total execution time of the processing task in seconds.
        - obs_strategy: GW_alert.ObservationStrategy
            The observation strategy used for the processing.
        - telescopes: list[str]
            List of telescopes involved in the gwemopt task.
        - tiles_plan: dict[str, Table | None]
            A dictionary mapping telescope names to their respective tiles plan.
        - path_gw_alert: str
            The path to the gwemopt results folder on OwnCloud.

    Returns
    -------
    SlackResponse
        The response from the Slack API after posting the message.

    Notes
    -----
    This function builds a message using the provided `build_msg_function` and sends it to the
    specified Slack channel using the provided `slack_client`. The message can be posted in a
    thread if `thread_ts` is provided. Additional keyword arguments can be passed to the
    `build_msg_function` to customize the message content, such as task ID, execution time,
    observation strategy, telescopes, tiles plan, and path to the GW alert folder on OwnCloud.
    """

    msg = build_msg_function(gw_alert, **kwargs)

    response = post_msg_on_slack(
        slack_client,
        channel,
        [msg],
        thread_ts=thread_ts,
        logger=logger,
        verbose=False,
    )

    logger.info(f"Alert sent to Slack channel: {channel}")

    return response
