import uuid

from celery import chord
from gcn_kafka import Consumer as KafkaConsumer
from yarl import URL

from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import (
    build_gwalert_data_msg,
    build_gwalert_notification_msg,
    new_alert_on_slack,
)
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
        path_gw_alert = f"Candidates/GW/{gw_alert.event_id}"
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

        gw_alert = GW_alert(
            notice,
            self.gcn_stream.gcn_config["THRESHOLD"],
        )

        if gw_alert.is_real_observation:
            self.logger.info("Significant alert detected")
            # Initialize the workflow for the significant alert
            # This includes sending the initial alert to Slack, creating the ownCloud folder, and saving the
            # alert in the database
            # If the alert already exists in the database, it will increment the reception count and set
            # the thread timestamp if it is not already set.

            score, _, _ = gw_alert.gw_score()
            is_ready_for_processing = score > 1

            gw_alert_db, owncloud_alert_url, gw_thread_ts = (
                self._handle_significant_alert(gw_alert, is_ready_for_processing)
            )

            if is_ready_for_processing:
                # Process the significant alert with the automatic gwemopt process
                self.automatic_gwemopt_process(
                    gw_alert_db, gw_alert.thresholds, owncloud_alert_url, gw_thread_ts
                )

            else:
                self.logger.info(
                    f"Alert {gw_alert.event_id} is below the automatic gwemopt score, score: {score}, skipping processing."
                )
                return

        else:
            return

    def push_new_alert_in_db(self, gw_alert: GW_alert) -> GW_alert_DB:
        """
        Push a new GW alert into the database or increment the reception count if it already exists.
        This method performs the following steps:
        1. Checks if the alert already exists in the database by its trigger ID.
        2. If it does not exist, creates a new entry in the database with reception count 1.
        3. If it exists, creates a new entry with the same trigger ID, increments the reception count, updates the thread timestamp if it is not already set and changes the payload JSON.
        4. Commits the changes to the database.

        Parameters
        ----------
        gw_alert : GW_alert
            The GW alert object containing event information and thresholds.

        Returns
        -------
        gw_alert_db : GW_alert_DB
            The GW alert database object representing the alert in the database.
        """
        gw_alert_db = GW_alert_DB.get_last_by_trigger_id(
            self.gcn_stream.session_local, gw_alert.event_id
        )
        if gw_alert_db is None:
            gw_alert_db = GW_alert_DB(
                triggerId=gw_alert.event_id,
                thread_ts=None,
                reception_count=1,
                payload_json=gw_alert.gw_dict,
            )
            self.gcn_stream.session_local.add(gw_alert_db)
            self.gcn_stream.session_local.commit()
            self.logger.info(
                f"New alert {gw_alert.event_id} added to the database with reception count 1."
            )
        else:
            gw_alert_db_bis = GW_alert_DB(
                triggerId=gw_alert.event_id,
                thread_ts=gw_alert_db.thread_ts,
                reception_count=gw_alert_db.reception_count + 1,
                payload_json=gw_alert.gw_dict,
            )
            self.gcn_stream.session_local.add(gw_alert_db_bis)
            self.gcn_stream.session_local.commit()
            self.logger.info(
                f"Alert {gw_alert.event_id} already exists in the database, incrementing reception count to {gw_alert_db_bis.reception_count}."
            )
            gw_alert_db = gw_alert_db_bis

        return gw_alert_db

    def _handle_significant_alert(
        self, gw_alert: GW_alert, is_ready_for_processing: bool
    ) -> tuple[GW_alert_DB, str, str]:
        """
        Handles the starting of the workflow for a significant alert (slack, owncloud, DB).
        This method performs the following steps:
        1. Pushes the new alert into the database or increments the reception count if it already exists.
        2. If the alert is new, sends a notification message to Slack and sets the thread timestamp.
        3. Initializes the ownCloud folders for the alert.
        4. Sends the main alert information to Slack in a thread.

        Parameters
        ----------
        gw_alert : GW_alert
            The significant GW alert object containing event information and thresholds.
        is_ready_for_processing : bool
            Indicates whether the alert is ready for processing based on its significance score.

        Returns
        -------
        tuple[GW_alert_DB, str, str]:
            A tuple containing:
            - gw_alert_db: The GW alert database object representing the alert in the database.
            - owncloud_alert_url: The URL of the alert folder on ownCloud.
            - gw_thread_ts: The thread timestamp for the alert on Slack, used to link the alert messages.
        """
        gw_alert_db: GW_alert_DB = self.push_new_alert_in_db(gw_alert)

        self.logger.info(
            f"Alert {gw_alert.event_id} with triggerId {gw_alert_db.triggerId} "
            f"and reception count {gw_alert_db.reception_count}"
        )

        if gw_alert_db.thread_ts is None:
            notif_alert_response = new_alert_on_slack(
                gw_alert,
                build_gwalert_notification_msg,
                self.gcn_stream.slack_client,
                channel=self.gw_alert_channel,
                logger=self.logger,
            )

            gw_alert_db.set_thread_ts(
                notif_alert_response["ts"], self.gcn_stream.session_local
            )

            self.logger.info(
                f"Thread timestamp set for alert {gw_alert.event_id}: {notif_alert_response['ts']}"
            )

        gw_thread_ts = gw_alert_db.thread_ts

        # Initialize ownCloud folders for this alert
        path_gw_alert, owncloud_alert_url = self.init_owncloud_folders(gw_alert)

        self.logger.info(f"Folder created on ownCloud, url: {owncloud_alert_url}")

        # Send main alert info to Slack (in thread)
        data_message_response = new_alert_on_slack(
            gw_alert,
            build_gwalert_data_msg,
            self.gcn_stream.slack_client,
            channel=self.gw_alert_channel,
            logger=self.logger,
            thread_ts=gw_thread_ts,
            path_gw_alert=path_gw_alert,
            nb_alert_received=gw_alert_db.reception_count,
            add_obs_plan_button=not is_ready_for_processing,
        )

        gw_alert_db.set_message_ts(
            data_message_response["ts"], self.gcn_stream.session_local
        )

        self.logger.info("Send gw alert to slack")

        return gw_alert_db, owncloud_alert_url, gw_thread_ts

    def automatic_gwemopt_process(
        self,
        gw_alert_db: GW_alert_DB,
        threshold_config: dict[str, float | int],
        owncloud_alert_url: URL,
        gw_thread_ts: str,
    ) -> None:
        """
        Process a significant GW alert by generating an observation plan using the GWEMOPT task.
        This method performs the following steps:
        1. Logs the processing of the significant alert.
        2. Saves the alert notice to disk for transfer to the Celery worker.
        3. Initializes the ownCloud folders for the alert.
        4. Constructs a list of Celery tasks for each GWEMOPT configuration (telescopes, number of tiles, observation strategy).
        5. Sends the tasks to the Celery worker using a chord, which will execute the tasks in parallel and trigger a post-processing task upon
        completion.

        Parameters
        ----------
        gw_alert_db : GW_alert_DB
            The GW alert database object containing event information and thresholds.
        threshold_config : dict[str, float | int]
            The configuration dictionary containing thresholds for the GW alert.
        owncloud_alert_url : URL
            The URL of the alert folder on ownCloud where the notice will be saved.
        gw_thread_ts : str
            The thread timestamp for the alert on Slack, used to link the alert messages.

        Raises
        ------
        Exception
            Any exception during the processing is logged and re-raised.
        """
        self.logger.info(
            f"Processing significant alert {gw_alert_db.triggerId} with score > 1, Observation plan will be generated."
        )

        self.logger.info("Sending gwemopt task to celery worker")

        telescopes_list = self.gcn_stream.gcn_config["GWEMOPT"]["telescopes"]
        number_of_tiles = self.gcn_stream.gcn_config["GWEMOPT"]["number_of_tiles"]
        observation_strategy = self.gcn_stream.gcn_config["GWEMOPT"][
            "observation_strategy"
        ]

        # Indicate that the alert is being processed
        # This is used to prevent multiple processes from running the same alert
        gw_alert_db.is_process_running = True
        self.gcn_stream.session_local.commit()
        self.logger.info(
            f"Alert {gw_alert_db.triggerId} is being processed, setting is_process_running to True"
        )
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
                gw_alert_db.id_gw,
                "_".join(
                    [
                        gw_alert_db.triggerId,
                        obs_strat,
                        "_".join(tel_list),
                        uuid.uuid4().hex,
                    ]
                ),
                self.gcn_stream.gcn_config["PATH"]["celery_task_log_path"],
                threshold_config,
                obs_strat,
                gw_thread_ts,
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
                if message.error():
                    self.logger.error(message.error())
                    continue
                try:
                    self.process_alert(notice=message.value())
                    self.commit(message)
                except Exception as err:
                    self.logger.error(err)
                    raise err
