import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import dotenv_values
from fink_utils.slack_bot.bot import init_slackbot
from flask import Flask, g, jsonify
from sqlalchemy import text

from grandma_gcn.database.session import get_session_local
from grandma_gcn.flask_listener.slack_listener import slack_bp
from grandma_gcn.gcn_stream.stream import load_gcn_config


def create_app(config: dict = None) -> Flask:
    """
    Create and configure the Flask application using .env values.

    Parameters
    ----------
    config : dict, optional
        A dictionary of configuration options to override defaults.

    Returns
    -------
    Flask
        The initialized Flask application.
    """
    env = dotenv_values(".env")  # Load key-value pairs from .env file
    # Initialize logger
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        formatter = logging.Formatter(
            "[Slack] %(asctime)s - %(levelname)s - %(message)s"
        )

        # Console
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        # Files with automatic rotation (5 MB max, 5 backups)
        flask_log_path = Path(env.get("SLACK_LOG_FILE", "logs/slack.logs"))
        flask_log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            flask_log_path, maxBytes=5 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    app = Flask(__name__)

    root_logger.setLevel(logging.DEBUG if app.config["DEBUG"] else logging.INFO)
    # Reuse handlers for Flask's logger
    for handler in root_logger.handlers:
        app.logger.addHandler(handler)
    app.logger.setLevel(root_logger.level)

    # Load config from .env
    app.config["DEBUG"] = env.get("FLASK_DEBUG", "0") == "1"
    app.config["SECRET_KEY"] = env.get("SECRET_KEY", "changeme")

    gcn_config = load_gcn_config(
        Path(env.get("GCN_STREAM_CONFIG_PATH", "gcn_stream_config.toml")),
        logger=app.logger,
    )
    app.config["GCN_CONFIG"] = gcn_config

    # Override with provided config
    if config:
        app.config.update(config)

    @app.before_request
    def before_request():
        g.db = get_session_local()()
        slack_secret = env.get("SLACK_SIGNING_SECRET", "changeme")
        g.slack_secret = slack_secret
        slack_client = init_slackbot()
        g.slack_client = slack_client

    @app.teardown_request
    def teardown_request(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # Register health route
    @app.route("/ping")
    def ping():
        return jsonify({"message": "pong"})

    @app.route("/")
    def index():
        return jsonify({"message": "Hello from grandma-bot !"})

    @app.route("/db-ping")
    def db_ping():
        db = g.db
        result = db.execute(text("SELECT 1")).scalar()
        return jsonify({"db_status": result})

    # Register slack blueprint
    app.register_blueprint(slack_bp, url_prefix="/api/slack")

    return app
