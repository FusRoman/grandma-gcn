"""
Celery worker for fetching and parsing SWIFT BAT GRB HTML analysis results.

This worker is scheduled with a delay (typically 3 minutes) after a SWIFT GRB
trigger is received, allowing time for the HTML analysis page to be generated
on the SWIFT website.
"""

import json
from pathlib import Path
import requests
from celery import current_task
from fink_utils.slack_bot.bot import init_slackbot

from grandma_gcn.parse_swift_html import format_swift_message, parse_swift_grb_html
from grandma_gcn.worker.celery_app import celery
from grandma_gcn.worker.gwemopt_worker import setup_task_logger


@celery.task(
    name="fetch_and_post_swift_analysis",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": 3,
        "countdown": 300,
    },  # Retry up to 3 times, wait 5 min between retries
    retry_backoff=True,
)
def fetch_and_post_swift_analysis(
    self,
    trigger_id: int,
    thread_ts: str,
    channel: str,
    path_log: str = "/tmp",
):
    """
    Fetch SWIFT BAT GRB HTML analysis and post results to Slack thread.

    This task is scheduled to run 3 minutes after a SWIFT GRB trigger is received,
    giving the SWIFT pipeline time to generate the HTML analysis page.

    Args:
        trigger_id: SWIFT trigger ID (eg. 1423875)
        thread_ts: Slack thread timestamp to post the results to
        channel: Slack channel to post results to
        path_log: Path to log directory (default: /tmp)

    Raises:
        Exception: If HTML parsing fails or Slack posting fails (will trigger retry)
    """
    task_id = current_task.request.id
    logger, _ = setup_task_logger(
        f"swift_html_analysis_{trigger_id}", Path(path_log), task_id
    )

    logger.info(f"Starting SWIFT HTML analysis task for trigger {trigger_id}")
    logger.info(f"Fetching SWIFT HTML analysis for trigger {trigger_id}")

    try:
        params = parse_swift_grb_html(trigger_id)

        if not any(
            params.get(key) for key in ["t90", "hardness_ratio", "fluence_15_150"]
        ):
            logger.warning(
                f"No valid data extracted from SWIFT HTML for trigger {trigger_id}"
            )
            return

        msg = format_swift_message(params, trigger_id=trigger_id)

        if not msg:
            logger.warning(f"Empty message generated for trigger {trigger_id}")
            return

        slack_client = init_slackbot()

        logger.info(
            f"Posting SWIFT analysis to Slack channel {channel}, thread {thread_ts}"
        )

        blocks_json = json.dumps(msg.blocks["blocks"])
        response = slack_client.chat_postMessage(
            channel=channel,
            text=f"SWIFT BAT Detailed Analysis for trigger {trigger_id}",
            blocks=blocks_json,
            thread_ts=thread_ts,
        )

        if response.get("ok"):
            logger.info(f"Successfully posted SWIFT analysis for trigger {trigger_id}")
        else:
            error_msg = response.get("error", "Unknown error")
            logger.error(f"Failed to post to Slack: {error_msg}")
            raise Exception(f"Slack API error: {error_msg}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(
                f"SWIFT HTML page not found for trigger {trigger_id} (404). "
                f"Will retry {self.request.retries + 1}/{self.max_retries} times."
            )
        else:
            logger.error(
                f"HTTP error {e.response.status_code} for trigger {trigger_id}: {e}",
                exc_info=True,
            )
        raise
    except Exception as e:
        logger.error(
            f"Error processing SWIFT analysis for trigger {trigger_id}: {e}",
            exc_info=True,
        )
        raise


@celery.task(name="test_swift_html_parsing", bind=True)
def test_swift_html_parsing(self, trigger_id: int, path_log: str = "/tmp"):
    """
    Test task for parsing SWIFT HTML without posting to Slack.

    Args:
        trigger_id: SWIFT trigger ID to test
        path_log: Path to log directory (default: /tmp)

    Returns:
        dict: Parsed parameters from the HTML
    """
    task_id = current_task.request.id
    logger, _ = setup_task_logger(
        f"swift_html_test_{trigger_id}", Path(path_log), task_id
    )

    logger.info(f"Testing SWIFT HTML parsing for trigger {trigger_id}")

    try:
        params = parse_swift_grb_html(trigger_id)
        msg = format_swift_message(params)

        logger.info(f"Parsed parameters: {params}")
        logger.info(f"Formatted message blocks: {msg.blocks}")

        return {"success": True, "params": params, "blocks": msg.blocks}
    except Exception as e:
        logger.error(f"Test failed for trigger {trigger_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
