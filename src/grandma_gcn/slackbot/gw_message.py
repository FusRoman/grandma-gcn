from fink_utils.slack_bot.msg_builder import Message
from fink_utils.slack_bot.bot import init_slackbot, post_msg_on_slack

from grandma_gcn.gcn_stream.gcn_logging import init_logging


def build_gwalert_msg() -> Message:
    msg = Message()
    msg.add_header("Grandma Slack Test")
    msg.add_divider()

    return msg


if __name__ == "__main__":

    logger = init_logging("test_slack_bot")
    slack_client = init_slackbot(logger)

    msg = build_gwalert_msg()

    post_msg_on_slack(
        slack_client,
        "#test_gwalerts",
        [msg],
        logger=logger,
        verbose=True,
    )
