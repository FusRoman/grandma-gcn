from pathlib import Path
from typing import Any

from grandma_gcn.gcn_stream.consumer import Consumer
import tomli
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine, init_logging
from fink_utils.slack_bot.bot import init_slackbot


class GCNStream:
    def __init__(
        self,
        path_gcn_config: Path,
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

    def run(self, test: bool = False) -> None:
        """
        Run the polling infinite loop of the GCN stream with periodic configuration checks
        """

        gcn_consumer = Consumer(gcn_stream=self, logger=self.logger)

        self.logger.info("Starting GCN stream consumer")
        while True:
            gcn_consumer.start_poll_loop()
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


def main(gcn_config_path: str = "instance/gcn_config.toml") -> None:
    """
    Launch the GCN stream, an infinite loop waiting for notices from the GCN network.
    """
    logger = init_logging(logger_name="gcn_stream")
    gcn_stream = GCNStream(Path(gcn_config_path), logger, restart_queue=True)
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
    args = parser.parse_args()
    main(gcn_config_path=args.gcn_config_path)
