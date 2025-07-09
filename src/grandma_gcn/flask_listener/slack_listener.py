import hashlib
import hmac
import json
import logging
import time

from dotenv import dotenv_values
from flask import Blueprint, abort, jsonify, request

# Configuration du logger
logger = logging.getLogger("slack")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[Slack] %(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

slack_bp = Blueprint("slack", __name__)
env = dotenv_values(".env")
SLACK_SECRET = env.get("SLACK_SIGNING_SECRET", "changeme")


def verify_slack_request(req):
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
            SLACK_SECRET.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest()
    )

    logger.debug(f"Generated signature: {my_signature}")

    if not hmac.compare_digest(my_signature, signature):
        logger.warning("Invalid signature")
        return False

    return True


@slack_bp.route("/actions", methods=["POST"])
def handle_actions():
    logger.info("Received POST to /api/slack/actions")

    if not verify_slack_request(request):
        logger.error("Request verification failed")
        abort(400, "Invalid Slack signature")

    try:
        payload = json.loads(request.form["payload"])
        logger.debug(f"Payload received: {json.dumps(payload, indent=2)}")

        action = payload["actions"][0]["action_id"]
        user = payload["user"]["username"]

        logger.info(f"User `{user}` clicked button `{action}`")

        # 👉 Traitement réel ici :
        # lancer_observation_plan() ou envoyer à Celery

        return jsonify(
            {"text": f"🛰️ Running observation plan as requested by `{user}`."}
        )

    except Exception as e:
        logger.exception("Failed to process Slack action")
        abort(500, f"Internal error: {e}")
