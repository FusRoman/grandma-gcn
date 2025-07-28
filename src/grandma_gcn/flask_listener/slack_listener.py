import hashlib
import hmac
import json
import logging
import time

from flask import Blueprint, abort, current_app, g, jsonify, request

from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB
from grandma_gcn.gcn_stream.automatic_gwemopt import automatic_gwemopt_process
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import (
    manual_gwemopt_notification,
    new_alert_on_slack,
)

slack_bp = Blueprint("slack", __name__)

ALLOWED_ACTIONS = ["run_obs_plan"]  # Run Observation Plan


def verify_slack_request(req):
    logger = logging.getLogger("slack")

    signature = req.headers.get("X-Slack-Signature", "")
    timestamp = req.headers.get("X-Slack-Request-Timestamp", "")

    logger.debug(f"Signature header: {signature}")
    logger.debug(f"Timestamp header: {timestamp}")

    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.warning("Timestamp too old – possible replay attack.")
            return False
    except Exception as e:
        logger.error(f"Invalid timestamp format: {e}")
        return False

    base_string = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    my_signature = (
        "v0="
        + hmac.new(
            g.slack_secret.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest()
    )

    logger.debug(f"Generated signature: {my_signature}")

    if not hmac.compare_digest(my_signature, signature):
        logger.warning("Invalid signature")
        return False

    return True


@slack_bp.route("/actions", methods=["POST"])
def handle_actions():
    logger = logging.getLogger("slack")

    logger.info("Received POST to /api/slack/actions")

    if not verify_slack_request(request):
        logger.error("Request verification failed")
        abort(400, "Invalid Slack signature")

    try:
        payload = json.loads(request.form["payload"])
        logger.debug(f"Payload received: {json.dumps(payload, indent=2)}")

        action_id = payload["actions"][0]["action_id"]
        user = payload["user"]["username"]
        user_id = payload["user"]["id"]

        logger.info(f"User `{user}` clicked button `{action_id}`")

        if action_id not in ALLOWED_ACTIONS:
            logger.info(f"Ignored action `{action_id}`, not in {ALLOWED_ACTIONS}")
            return jsonify({"text": f"Action `{action_id}` ignored."})

        db_session = g.db

        gw_alert_db = GW_alert_DB.get_by_message_ts(
            db_session, payload["message"]["ts"]
        )

        gw_alert = GW_alert.from_db_model(
            gw_alert_db, thresholds=current_app.config["GCN_CONFIG"]["THRESHOLD"]
        )

        logger.debug(f"Found GW alert in DB: {gw_alert_db}")
        logger.debug(f"Converted GW alert: {gw_alert}")

        if gw_alert_db.is_process_running:
            response = g.slack_client.conversations_open(users=user_id)
            channel_id = response["channel"]["id"]

            text = (
                f":warning: Alert *{gw_alert_db.triggerId}* has already been processed "
                f"or is currently running.\n\n"
                f"Please refer to <#{current_app.config['GCN_CONFIG']['Slack']['gw_alert_channel_id']}> for status and updates."
            )

            g.slack_client.chat_postMessage(channel=channel_id, text=text)

            logger.info(
                f"Alert {gw_alert_db.triggerId} is already being processed, skipping."
            )
            return jsonify(
                {"text": f"Alert `{gw_alert_db.triggerId}` is already being processed."}
            )

        new_alert_on_slack(
            gw_alert,
            manual_gwemopt_notification,
            g.slack_client,
            channel=current_app.config["GCN_CONFIG"]["Slack"]["gw_alert_channel"],
            logger=logger,
            thread_ts=gw_alert_db.thread_ts,
            user=user,
        )

        automatic_gwemopt_process(
            current_app.config["GCN_CONFIG"],
            gw_alert_db,
            db_session,
            current_app.config["GCN_CONFIG"]["THRESHOLD"],
            current_app.config["GCN_CONFIG"]["Slack"]["gw_alert_channel"],
            current_app.config["GCN_CONFIG"]["Slack"]["gw_alert_channel_id"],
            logger,
        )

        return jsonify(
            {"text": f"🛰️ Running observation plan as requested by `{user}`."}
        )

    except Exception as e:
        logger.exception("Failed to process Slack action")
        abort(500, f"Internal error: {e}")
