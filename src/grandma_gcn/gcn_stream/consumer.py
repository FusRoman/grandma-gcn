from celery import chord
from gcn_kafka import Consumer as KafkaConsumer
import uuid

from yarl import URL

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import build_gwalert_msg, new_alert_on_slack
from grandma_gcn.worker.gwemopt_worker import gwemopt_post_task, gwemopt_task
from grandma_gcn.worker.owncloud_client import OwncloudClient


class Consumer(KafkaConsumer):
    def __init__(self, gcn_stream, logger: LoggerNewLine) -> None:
        self.logger = logger
        self.logger.info("Starting GCN stream consumer")

        super().__init__(
            config=gcn_stream.gcn_config["KAFKA_CONFIG"],
            client_id=gcn_stream.gcn_config["CLIENT"]["id"],
            client_secret=gcn_stream.gcn_config["CLIENT"]["secret"],
        )

        self.owncloud_client = OwncloudClient(gcn_stream.gcn_config.get("OWNCLOUD"))

        self.gcn_stream = gcn_stream

        topics = gcn_stream.gcn_config["GCN_TOPICS"]["topics"]

        self.gw_alert_channel = gcn_stream.gcn_config["Slack"]["gw_alert_channel"]
        self.gw_channel_id = gcn_stream.gcn_config["Slack"]["gw_alert_channel_id"]

        # Subscribe to topics and receive alerts
        if gcn_stream.restart_queue:
            self.subscribe(
                topics,
                on_assign=Consumer.assign_partition,
            )
        else:
            self.subscribe(topics)

    @staticmethod
    def assign_partition(consumer: "Consumer", partitions) -> None:
        """
        Function to reset offsets when (re)polling
        It must be passed when subscribing to a topic:
            `consumer.subscribe(topics, on_assign=my_assign)`

        Parameters
        ----------
        consumer: confluent_kafka.Consumer
            Kafka consumer
        partitions: Kafka partitions
            Internal object to deal with partitions
        """
        for p in partitions:
            p.offset = 0
        consumer.assign(partitions)

    def init_owncloud_folders(self, gw_alert: GW_alert) -> tuple[str, URL]:
        """
        Initialize the ownCloud folders for the given GW alert.

        Parameters
        ----------
        gw_alert: The GW alert object containing event information.

        Returns
        -------
        tuple[str, URL]: The path to the alert folder on ownCloud and the URL of the alert folder.
        """
        path_gw_alert = "Candidates/GW/{}".format(gw_alert.event_id)
        # create a new folder on ownCloud for this alert
        path_owncloud_gw = self.owncloud_client.mkdir(path_gw_alert)

        self.logger.info(f"Folder {path_owncloud_gw} successfully created on ownCloud")
        path_gwemopt = path_gw_alert + "/GWEMOPT"
        path_images = path_gw_alert + "/IMAGES"
        path_knc_images = path_gw_alert + "/KNC_IMAGES"
        path_logbook = path_gw_alert + "/LOGBOOK"
        path_voevents = path_gw_alert + "/VOEVENTS"

        # create subfolders for gwemopt, images, knc_images, logbook and voevents
        path_owncloud_gwemopt = self.owncloud_client.mkdir(path_gwemopt)
        self.logger.info(
            f"Folder {path_owncloud_gwemopt} successfully created on ownCloud"
        )

        # create subfolder for the alert type where the gwemopt products will be stored
        path_alert = path_gwemopt + f"/{gw_alert.event_type.value}_{uuid.uuid4().hex}"
        url_owncloud_alert = self.owncloud_client.mkdir(path_alert)
        self.logger.info(
            f"Folder {url_owncloud_alert} successfully created on ownCloud"
        )

        path_owncloud_images = self.owncloud_client.mkdir(path_images)
        self.logger.info(
            f"Folder {path_owncloud_images} successfully created on ownCloud"
        )
        path_owncloud_knc_images = self.owncloud_client.mkdir(path_knc_images)
        self.logger.info(
            f"Folder {path_owncloud_knc_images} successfully created on ownCloud"
        )
        path_owncloud_logbook = self.owncloud_client.mkdir(path_logbook)
        self.logger.info(
            f"Folder {path_owncloud_logbook} successfully created on ownCloud"
        )
        path_owncloud_voevents = self.owncloud_client.mkdir(path_voevents)
        self.logger.info(
            f"Folder {path_owncloud_voevents} successfully created on ownCloud"
        )

        return path_gw_alert, url_owncloud_alert

    def process_alert(self, notice: bytes) -> None:
        """
        Process a GW alert notice received from the Kafka stream.

        This method performs the following steps:
        1. Parses the alert notice and computes its significance score using configured thresholds.
        2. If the alert is significant (score > 1):
            - Saves the notice as a JSON file in the configured notice directory.
            - Initializes a dedicated folder structure for the event on OwnCloud (including GWEMOPT, images, logbook, etc.).
            - Sends a formatted alert message to the configured Slack channel.
            - For each GWEMOPT configuration (telescopes, number of tiles, strategy), dispatches a Celery task to generate observation plans in parallel.
            - All GWEMOPT tasks are grouped in a Celery chord, with a post-processing task triggered upon completion.
        3. Logs all major actions and errors for traceability.

        Parameters
        ----------
        notice : bytes
            The alert notice in bytes, as received from the Kafka stream.

        Raises
        ------
        Exception
            Any exception during processing is logged and re-raised.
        """
        self.logger.info("Processing alert")

        gw_alert = GW_alert(
            notice,
            self.gcn_stream.gcn_config["THRESHOLD"],
        )
        score, _, _ = gw_alert.gw_score()
        if score > 1:
            self.logger.info("Significant alert detected")

            # save the notice on disk to transfer it to the celery worker
            path_notice = gw_alert.save_notice(self.gcn_stream.notice_path)

            self.logger.info(f"Notice saved at {path_notice}")

            # Initialize ownCloud folders for this alert
            path_gw_alert, owncloud_alert_url = self.init_owncloud_folders(gw_alert)

            self.logger.info(f"Folder created on ownCloud, url: {owncloud_alert_url}")

            # send a message to Slack with the alert information
            new_alert_response = new_alert_on_slack(
                gw_alert,
                build_gwalert_msg,
                self.gcn_stream.slack_client,
                channel=self.gw_alert_channel,
                logger=self.logger,
                path_gw_alert=path_gw_alert,
            )

            self.logger.info("Send gw alert to slack")

            self.logger.info("Sending gwemopt task to celery worker")

            telescopes_list = self.gcn_stream.gcn_config["GWEMOPT"]["telescopes"]
            number_of_tiles = self.gcn_stream.gcn_config["GWEMOPT"]["number_of_tiles"]
            observation_strategy = self.gcn_stream.gcn_config["GWEMOPT"][
                "observation_strategy"
            ]

            # construct a list of tasks for each sublist of telescopes, number of tiles and observation strategy
            gwemopt_tasks = [
                gwemopt_task.s(
                    tel_list,
                    nb_tiles_list,
                    self.gcn_stream.gcn_config["GWEMOPT"]["nside_flat"],
                    self.gw_alert_channel,
                    self.gw_channel_id,
                    self.gcn_stream.gcn_config["OWNCLOUD"],
                    str(owncloud_alert_url),
                    str(path_notice),
                    "_".join(
                        [
                            gw_alert.event_id,
                            obs_strat,
                            "_".join(tel_list),
                            uuid.uuid4().hex,
                        ]
                    ),
                    self.gcn_stream.gcn_config["PATH"]["celery_task_log_path"],
                    gw_alert.thresholds,
                    obs_strat,
                    new_alert_response["ts"],
                    self.gcn_stream.gcn_config["GWEMOPT"]["path_galaxy_catalog"],
                    self.gcn_stream.gcn_config["GWEMOPT"]["galaxy_catalog"],
                )
                for tel_list, nb_tiles_list, obs_strat in zip(
                    telescopes_list,
                    number_of_tiles,
                    observation_strategy,
                )
            ]

            chord(gwemopt_tasks)(
                gwemopt_post_task.s(
                    owncloud_config=self.gcn_stream.gcn_config["OWNCLOUD"],
                )
            )

    def start_poll_loop(
        self, interval_between_polls: int = 1, max_retries: int = 120
    ) -> None:
        """
        Poll for messages from the Kafka stream with a timeout. The maximum duration of the polling is defined by the
        interval_between_polls multiplied by the max_retries.

        Args:
            interval_between_polls (int, optional): Interval between polling attempts. Defaults to 1.
            max_retries (int, optional): Maximum number of polling attempts. Defaults to 120.
        """
        for _ in range(max_retries):
            message = self.poll(timeout=interval_between_polls)
            if message is not None:

                self.logger.info("-- A new notice has arrived --")
                self.logger.info(f"topic: {message.topic()}")
                self.logger.info(f"current offset: {message.offset()}")
                if message.error():
                    self.logger.error(message.error())
                    continue
                try:
                    self.process_alert(notice=message.value())
                    self.commit(message)
                except Exception as err:
                    self.logger.error(err)
                    raise err
