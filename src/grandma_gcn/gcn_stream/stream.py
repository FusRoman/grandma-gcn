from pathlib import Path
from typing import Any

import tomli
from dotenv import dotenv_values
from fink_utils.slack_bot.bot import init_slackbot
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from grandma_gcn.database.init_db import init_db
from grandma_gcn.gcn_stream.consumer import Consumer
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine, init_logging


class GCNStream:
    def __init__(
        self,
        path_gcn_config: Path,
        engine: Engine,
        session_local: Session,
        logger: LoggerNewLine,
        restart_queue: bool = False,
    ) -> None:
        """
        Initialize the GCN stream that will query configurations from the API

        Parameters
        ----------
        restart_queue : bool, optional
            restart the polling of the gcn message from the beginning (offset 0), by default False
        """
        self._engine = engine
        self._session_local = session_local

        self.logger = logger
        self.path_config = path_gcn_config

        self._gcn_config = load_gcn_config(self.path_config, logger=self.logger)

        # ensure log path exists
        logfile = Path(self._gcn_config["PATH"]["gcn_stream_log_path"])
        if not logfile.parent.exists():
            logfile.parent.mkdir(parents=True, exist_ok=True)

        self.logger.setFileHandler(logfile)

        self.restart_queue = restart_queue

        self.slack_client = init_slackbot(self.logger)

        self.notice_path = Path(self._gcn_config["PATH"]["notice_path"])
        self.logger.info("GCN stream successfully initialized")

    @property
    def gcn_config(self) -> dict[str, Any]:
        return self._gcn_config

    @property
    def engine(self) -> Engine:
        """
        Get the SQLAlchemy engine used to connect to the database
        """
        return self._engine

    @property
    def session_local(self) -> Session:
        """
        Get the SQLAlchemy session local used to create sessions
        """
        return self._session_local

    def run(self, test: bool = False) -> None:
        """
        Run the polling infinite loop of the GCN stream with periodic configuration checks
        """

        gcn_consumer = Consumer(gcn_stream=self, logger=self.logger)

        self.logger.info("Starting GCN stream consumer")
        while True:
            self.logger.info("GCN stream consumer is active, waiting for messages...")
            gcn_consumer.start_poll_loop(max_retries=3600)
            if test:
                break


def load_gcn_config(config_path: Path, logger: LoggerNewLine) -> dict[str, Any]:
    """
    Load the configuration file of the GCN stream.

    Parameters
    ----------
    config_path : Path
        The path of the gcn stream configuration

    Returns
    -------
    dict[str, Any]
        The dictionary containing the GCN stream configuration

    Exit
    ----
    Quit the program if the configuration file does not exist
    """
    if not config_path.exists():
        logger.error(f"Configuration file {config_path} does not exist.")
        exit(1)
    with open(config_path, "rb") as f:
        toml_dict = tomli.load(f)
    return toml_dict


def main(
    gcn_config_path: str = "instance/gcn_config.toml", restart_queue: bool = False
) -> None:
    """
    Launch the GCN stream, an infinite loop waiting for notices from the GCN network.
    """
    logger = init_logging(logger_name="gcn_stream")

    # initialize the sql database connection
    config = dotenv_values(".env")  # Load environment variables from .env file
    DATABASE_URL = config["SQLALCHEMY_DATABASE_URI"]
    engine, session_local = init_db(DATABASE_URL, logger=logger, echo=True)

    with session_local() as session:
        gcn_stream = GCNStream(
            Path(gcn_config_path), engine, session, logger, restart_queue=restart_queue
        )
        gcn_stream.run()


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Run the GCN stream")
    parser.add_argument(
        "--gcn-config-path",
        type=str,
        default="gcn_config.toml",
        help="Path to the GCN configuration file",
    )
    parser.add_argument(
        "--restart-queue",
        action="store_true",
        default=False,
        help="Restart the polling of the GCN message queue from the beginning (offset 0)",
    )
    args = parser.parse_args()
    main(gcn_config_path=args.gcn_config_path, restart_queue=args.restart_queue)
