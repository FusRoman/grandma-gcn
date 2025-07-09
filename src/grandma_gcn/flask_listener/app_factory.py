from dotenv import dotenv_values
from flask import Flask, jsonify

from grandma_gcn.flask_listener.slack_listener import slack_bp


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

    app = Flask(__name__)

    # Load config from .env
    app.config["DEBUG"] = env.get("FLASK_DEBUG", "0") == "1"
    app.config["SECRET_KEY"] = env.get("SECRET_KEY", "changeme")

    # Override with provided config
    if config:
        app.config.update(config)

    # Register health route
    @app.route("/ping")
    def ping():
        return jsonify({"message": "pong erivis"})

    @app.route("/")
    def index():
        return jsonify({"message": "Hello from Flask!"})

    # Register slack blueprint
    app.register_blueprint(slack_bp, url_prefix="/api/slack")

    return app
