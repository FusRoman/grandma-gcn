import uuid

from gcn_kafka import Consumer as KafkaConsumer
from yarl import URL

from grandma_gcn.database.grb_db import GRB_alert as GRB_alert_DB
from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB
from grandma_gcn.gcn_stream.automatic_gwemopt import automatic_gwemopt_process
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.gcn_stream.grb_alert import GRB_alert, Mission
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.grb_message import (
    build_svom_alert_msg,
    build_swift_alert_msg,
    send_grb_alert_to_slack,
)
from grandma_gcn.slackbot.gw_message import (
    build_gwalert_data_msg,
    build_gwalert_notification_msg,
    new_alert_on_slack,
)
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

        # GRB alert channel (optional, defaults to GW channel if not specified)
        self.grb_alert_channel = gcn_stream.gcn_config["Slack"].get(
            "grb_alert_channel", self.gw_alert_channel
        )

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

    def process_alert(self, notice: bytes, topic: str) -> None:
        """
        Process an alert notice received from the Kafka stream.
        Routes to GW or GRB processing based on the topic.

        Parameters
        ----------
        notice : bytes
            The alert notice in bytes, as received from the Kafka stream.
        topic : str
            The Kafka topic name (e.g., "igwn.gwalert", "gcn.notices.swift.bat.guano").

        Raises
        ------
        Exception
            Any exception during processing is logged and re-raised.
        """
        topic_lower = topic.lower()

        # Determine mission from topic
        if "swift" in topic_lower:
            self._process_grb_alert(notice, Mission.SWIFT)
        elif "svom" in topic_lower:
            self._process_grb_alert(notice, Mission.SVOM)
        else:
            self._process_gw_alert(notice)

    def _process_gw_alert(self, notice: bytes) -> None:
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

            gw_alert_db = self._handle_significant_alert(
                gw_alert, is_ready_for_processing
            )

            if is_ready_for_processing:
                # Process the significant alert with the automatic gwemopt process
                self._consumer_gwemopt_process(gw_alert_db, gw_alert.thresholds)

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
    ) -> GW_alert_DB:
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
        GW_alert_DB
            The GW alert database object representing the alert in the database.
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

        # Initialize ownCloud folders for this alert
        path_gw_alert, owncloud_alert_url = self.init_owncloud_folders(gw_alert)

        self.logger.info(f"Folder created on ownCloud, url: {owncloud_alert_url}")

        gw_alert_db.set_owncloud_url(
            str(owncloud_alert_url), self.gcn_stream.session_local
        )

        # Send main alert info to Slack (in thread)
        # The not is_ready_for_processing flag is used to determine whether to add the observation plan button
        # to the message. If the alert is not ready for processing, the button will be added to the message.
        data_message_response = new_alert_on_slack(
            gw_alert,
            build_gwalert_data_msg,
            self.gcn_stream.slack_client,
            channel=self.gw_alert_channel,
            logger=self.logger,
            thread_ts=gw_alert_db.thread_ts,
            path_gw_alert=path_gw_alert,
            nb_alert_received=gw_alert_db.reception_count,
            add_obs_plan_button=not is_ready_for_processing,
        )

        gw_alert_db.set_message_ts(
            data_message_response["ts"], self.gcn_stream.session_local
        )

        self.logger.info("Send gw alert to slack")

        return gw_alert_db

    def _consumer_gwemopt_process(
        self, gw_alert_db: GW_alert_DB, threshold_config: dict[str, float | int]
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

        Raises
        ------
        Exception
            Any exception during the processing is logged and re-raised.
        """

        automatic_gwemopt_process(
            gcn_stream_config=self.gcn_stream.gcn_config,
            gw_alert_db=gw_alert_db,
            db_session=self.gcn_stream.session_local,
            threshold_config=threshold_config,
            gw_alert_channel=self.gw_alert_channel,
            gw_channel_id=self.gw_channel_id,
            logger=self.logger,
        )

    def _get_pending_swift_alerts(
        self, all_alerts: list, initial_alert_id: int
    ) -> list:
        """Get pending Swift alerts excluding first BAT and XRT."""
        first_bat_id = None
        first_xrt_id = None
        for alert in all_alerts:
            if alert.packet_type == 61 and first_bat_id is None:
                first_bat_id = alert.id_grb
            if alert.packet_type == 67 and first_xrt_id is None:
                first_xrt_id = alert.id_grb

        return [
            alert
            for alert in all_alerts
            if alert.id_grb < initial_alert_id
            and alert.id_grb not in (first_bat_id, first_xrt_id)
        ]

    def _get_pending_svom_alerts(self, all_alerts: list, initial_alert_id: int) -> list:
        """Get pending SVOM alerts excluding first packet 202."""
        first_initial_id = None
        for alert in all_alerts:
            if alert.packet_type == 202:
                first_initial_id = alert.id_grb
                break

        return [
            alert
            for alert in all_alerts
            if alert.id_grb < initial_alert_id and alert.id_grb != first_initial_id
        ]

    def _send_pending_swift_update(
        self, trigger_id: str, alert_db, grb_alert: GRB_alert, thread_ts: str
    ) -> None:
        """Send a pending Swift update to the thread."""
        bat_alert = self._fetch_alert_from_db(trigger_id, 61)
        xrt_alert = self._fetch_alert_from_db(trigger_id, 67)
        uvot_alert = (
            self._fetch_alert_from_db(trigger_id, 81)
            if alert_db.packet_type == 81
            else None
        )

        send_grb_alert_to_slack(
            grb_alert=grb_alert,
            message_builder=build_swift_alert_msg,
            slack_client=self.gcn_stream.slack_client,
            channel=self.grb_alert_channel,
            logger=self.logger,
            thread_ts=thread_ts,
            bat_alert=bat_alert,
            xrt_alert=xrt_alert,
            uvot_alert=uvot_alert,
            is_xrt_update=alert_db.packet_type == 67,
            is_uvot_update=alert_db.packet_type == 81,
        )

    def _send_pending_svom_update(
        self, trigger_id: str, alert_db, grb_alert: GRB_alert, thread_ts: str
    ) -> None:
        """Send a pending SVOM update to the thread."""
        mxt_alert = (
            self._fetch_alert_from_db(trigger_id, 209)
            if alert_db.packet_type == 209
            else None
        )

        send_grb_alert_to_slack(
            grb_alert=grb_alert,
            message_builder=build_svom_alert_msg,
            slack_client=self.gcn_stream.slack_client,
            channel=self.grb_alert_channel,
            logger=self.logger,
            thread_ts=thread_ts,
            is_thread_update=True,
            mxt_alert=mxt_alert,
            is_mxt_update=alert_db.packet_type == 209,
        )

    def _send_pending_updates_to_thread(
        self, trigger_id: str, mission: Mission, thread_ts: str, initial_alert_id: int
    ) -> None:
        """
        Send any updates that arrived before the thread was created, in chronological order.

        Parameters
        ----------
        trigger_id : str
            The trigger ID of the GRB
        mission : Mission
            The mission (Swift or SVOM)
        thread_ts : str
            The thread timestamp to post updates to
        initial_alert_id : int
            The database ID of the alert that triggered the initial message
        """
        all_alerts = GRB_alert_DB.get_all_by_trigger_id(
            self.gcn_stream.session_local, trigger_id
        )

        # Get pending alerts based on mission
        if mission == Mission.SWIFT:
            pending_alerts = self._get_pending_swift_alerts(
                all_alerts, initial_alert_id
            )
        elif mission == Mission.SVOM:
            pending_alerts = self._get_pending_svom_alerts(all_alerts, initial_alert_id)
        else:
            pending_alerts = []

        for alert_db in pending_alerts:
            grb_alert = GRB_alert.from_db_model(alert_db)
            self.logger.info(
                f"Sending pending alert (packet {alert_db.packet_type}) for {trigger_id} in thread"
            )

            if mission == Mission.SWIFT:
                self._send_pending_swift_update(
                    trigger_id, alert_db, grb_alert, thread_ts
                )
            elif mission == Mission.SVOM:
                self._send_pending_svom_update(
                    trigger_id, alert_db, grb_alert, thread_ts
                )

    def _should_send_position_update(
        self, trigger_id: str, packet_type: int, update_name: str
    ) -> bool:
        """
        Check if a position update should be sent to Slack.
        Position updates (XRT, UVOT, MXT) are only sent if a thread exists.

        Parameters
        ----------
        trigger_id : str
            The trigger ID of the GRB
        packet_type : int
            The packet type number
        update_name : str
            Name of the update type (for logging)

        Returns
        -------
        bool
            True if update should be sent, False otherwise
        """
        existing_thread = (
            self.gcn_stream.session_local.query(GRB_alert_DB)
            .filter_by(triggerId=trigger_id)
            .filter(GRB_alert_DB.thread_ts.isnot(None))
            .first()
        )

        if existing_thread:
            self.logger.info(
                f"{update_name} alert {trigger_id} arrived, sending thread update"
            )
            return True
        else:
            self.logger.info(f"{update_name} alert {trigger_id} stored, no thread yet")
            return False

    def _fetch_alert_from_db(
        self, trigger_id: str, packet_type: int
    ) -> GRB_alert | None:
        """
        Fetch a GRB alert from database by trigger ID and packet type.

        Parameters
        ----------
        trigger_id : str
            The trigger ID of the GRB
        packet_type : int
            The packet type number

        Returns
        -------
        GRB_alert | None
            GRB_alert instance if found, None otherwise
        """
        alert_db = GRB_alert_DB.get_by_trigger_id_and_packet_type(
            self.gcn_stream.session_local, trigger_id, packet_type
        )
        return GRB_alert.from_db_model(alert_db) if alert_db else None

    def _schedule_swift_html_analysis(
        self, trigger_id: str, thread_ts: str, channel: str
    ) -> None:
        """
        Schedule a Celery task to fetch and parse SWIFT HTML analysis after 3 minutes.

        This gives the SWIFT pipeline time to generate the HTML analysis page.

        Parameters
        ----------
        trigger_id : str
            The SWIFT trigger ID
        thread_ts : str
            The Slack thread timestamp to post results to
        channel : str
            The Slack channel to post to
        """
        try:
            from grandma_gcn.worker.swift_html_worker import (
                fetch_and_post_swift_analysis,
            )

            path_log = self.gcn_stream.gcn_config.get("PATH", {}).get(
                "celery_task_log_path",
            )

            task = fetch_and_post_swift_analysis.apply_async(
                args=[int(trigger_id), thread_ts, channel, path_log], countdown=180
            )

            self.logger.info(
                f"Scheduled SWIFT HTML analysis task for trigger {trigger_id} "
                f"(task ID: {task.id}, will run in 3 minutes)"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to schedule SWIFT HTML analysis for trigger {trigger_id}: {e}"
            )

    def _get_existing_thread(self, trigger_id: str) -> GRB_alert_DB | None:
        """Get existing thread for a trigger_id if it exists."""
        return (
            self.gcn_stream.session_local.query(GRB_alert_DB)
            .filter_by(triggerId=trigger_id)
            .filter(GRB_alert_DB.thread_ts.isnot(None))
            .first()
        )

    def _should_send_swift_slack(self, grb_alert: GRB_alert) -> bool:
        """Determine if Swift alert should trigger a Slack message."""
        if grb_alert.packet_type == 61:  # BAT_GRB_POS_ACK
            xrt_exists = GRB_alert_DB.get_by_trigger_id_and_packet_type(
                self.gcn_stream.session_local, grb_alert.trigger_id, 67
            )
            if xrt_exists:
                self.logger.info(
                    f"BAT alert {grb_alert.trigger_id} arrived after XRT, sending combined message"
                )
                return True
            self.logger.info(
                f"Swift BAT alert {grb_alert.trigger_id} stored, waiting for XRT"
            )
            return False

        if grb_alert.packet_type == 67:  # XRT_POSITION
            bat_exists = GRB_alert_DB.get_by_trigger_id_and_packet_type(
                self.gcn_stream.session_local, grb_alert.trigger_id, 61
            )
            if bat_exists:
                self.logger.info(
                    f"XRT alert {grb_alert.trigger_id} arrived after BAT, sending combined message"
                )
                return True
            self.logger.info(
                f"Swift XRT alert {grb_alert.trigger_id} stored, waiting for BAT"
            )
            return False

        if grb_alert.packet_type == 81:  # UVOT_POSITION
            return self._should_send_position_update(grb_alert.trigger_id, 81, "UVOT")

        return True

    def _should_send_svom_slack(self, grb_alert: GRB_alert) -> bool:
        """Determine if SVOM alert should trigger a Slack message."""
        update_types = {204: "Slew accepted", 205: "Slew rejected", 209: "MXT"}
        if grb_alert.packet_type in update_types:
            return self._should_send_position_update(
                grb_alert.trigger_id,
                grb_alert.packet_type,
                update_types[grb_alert.packet_type],
            )
        return True

    def _build_swift_slack_kwargs(self, grb_alert: GRB_alert) -> dict:
        """Build kwargs for Swift Slack message."""
        bat_alert = self._fetch_alert_from_db(grb_alert.trigger_id, 61)
        xrt_alert_db = GRB_alert_DB.get_by_trigger_id_and_packet_type(
            self.gcn_stream.session_local, grb_alert.trigger_id, 67, get_first=True
        )
        xrt_alert = GRB_alert.from_db_model(xrt_alert_db) if xrt_alert_db else None
        uvot_alert = self._fetch_alert_from_db(grb_alert.trigger_id, 81)
        existing_thread = self._get_existing_thread(grb_alert.trigger_id)

        return {
            "bat_alert": bat_alert,
            "xrt_alert": xrt_alert,
            "uvot_alert": uvot_alert,
            "is_xrt_update": grb_alert.packet_type == 67
            and existing_thread is not None,
            "is_uvot_update": grb_alert.packet_type == 81
            and existing_thread is not None,
        }

    def _build_svom_slack_kwargs(self, grb_alert: GRB_alert) -> dict:
        """Build kwargs for SVOM Slack message."""
        mxt_alert = self._fetch_alert_from_db(grb_alert.trigger_id, 209)
        existing_thread = self._get_existing_thread(grb_alert.trigger_id)

        return {
            "is_thread_update": existing_thread is not None,
            "mxt_alert": mxt_alert,
            "is_mxt_update": grb_alert.packet_type == 209
            and existing_thread is not None,
        }

    def _process_grb_alert(self, notice: bytes, mission: Mission) -> None:
        """
        Process a GRB alert notice received from the Kafka stream.

        Parameters
        ----------
        notice : bytes
            The alert notice in bytes, as received from the Kafka stream.
        mission : Mission
            The mission that detected this GRB (determined from Kafka topic).
        """
        try:
            grb_alert = GRB_alert(notice, mission)

            self.logger.info(f"Processing GRB alert: {grb_alert.trigger_id}")
            self.logger.info(
                f"Mission: {grb_alert.mission.value}, "
                f"Packet Type: {grb_alert.packet_type}, "
                f"Position: RA={grb_alert.ra:.2f}, Dec={grb_alert.dec:.2f}, "
                f"Error: {grb_alert.ra_dec_error_arcmin:.2f} arcmin"
            )

            if not grb_alert.should_process_alert():
                self.logger.info(
                    f"GRB alert {grb_alert.trigger_id} filtered out "
                    f"(mission: {grb_alert.mission.value}, packet_type: {grb_alert.packet_type})"
                )
                return

            grb_alert_db = self._push_grb_alert_to_db(grb_alert)

            # Determine if we should send a Slack message
            if mission == Mission.SWIFT:
                should_send_slack = self._should_send_swift_slack(grb_alert)
                message_builder = build_swift_alert_msg
                kwargs = (
                    self._build_swift_slack_kwargs(grb_alert)
                    if should_send_slack
                    else {}
                )
            elif mission == Mission.SVOM:
                should_send_slack = self._should_send_svom_slack(grb_alert)
                message_builder = build_svom_alert_msg
                kwargs = (
                    self._build_svom_slack_kwargs(grb_alert)
                    if should_send_slack
                    else {}
                )
            else:
                return

            if not should_send_slack:
                return

            existing_thread = self._get_existing_thread(grb_alert.trigger_id)
            thread_ts = existing_thread.thread_ts if existing_thread else None

            response = send_grb_alert_to_slack(
                grb_alert=grb_alert,
                message_builder=message_builder,
                slack_client=self.gcn_stream.slack_client,
                channel=self.grb_alert_channel,
                logger=self.logger,
                thread_ts=thread_ts,
                **kwargs,
            )

            # Save thread timestamp if this is the first message
            if thread_ts is None:
                grb_alert_db.set_thread_ts(
                    response["ts"], self.gcn_stream.session_local
                )
                self.logger.info(
                    f"Thread timestamp set for GRB alert {grb_alert.trigger_id}: {response['ts']}"
                )

                self._send_pending_updates_to_thread(
                    grb_alert.trigger_id, mission, response["ts"], grb_alert_db.id_grb
                )

                if mission == Mission.SWIFT:
                    self._schedule_swift_html_analysis(
                        trigger_id=grb_alert.trigger_id,
                        thread_ts=response["ts"],
                        channel=self.grb_alert_channel,
                    )

        except Exception as err:
            self.logger.error(f"Error processing GRB alert: {err}")
            raise err

    def _push_grb_alert_to_db(self, grb_alert: GRB_alert) -> GRB_alert_DB:
        """
        Push a GRB alert into the database or increment the reception count if it already exists.

        Parameters
        ----------
        grb_alert : GRB_alert
            The GRB alert object containing event information.

        Returns
        -------
        GRB_alert_DB
            The GRB alert database object representing the alert in the database.
        """
        grb_alert_db = GRB_alert_DB.get_last_by_trigger_id(
            self.gcn_stream.session_local, grb_alert.trigger_id
        )

        if grb_alert_db is None:
            grb_alert_db = GRB_alert_DB(
                triggerId=grb_alert.trigger_id,
                mission=grb_alert.mission.value,
                packet_type=grb_alert.packet_type,
                ra=grb_alert.ra,
                dec=grb_alert.dec,
                error_deg=grb_alert.ra_dec_error,
                trigger_time=grb_alert.trigger_time_as_datetime,
                xml_payload=grb_alert.xml_string,
                thread_ts=None,
                reception_count=1,
            )
            self.gcn_stream.session_local.add(grb_alert_db)
            self.gcn_stream.session_local.commit()
            self.logger.info(
                f"New GRB alert {grb_alert.trigger_id} added to database with reception count 1."
            )
        else:
            grb_alert_db_new = GRB_alert_DB(
                triggerId=grb_alert.trigger_id,
                mission=grb_alert.mission.value,
                packet_type=grb_alert.packet_type,
                ra=grb_alert.ra,
                dec=grb_alert.dec,
                error_deg=grb_alert.ra_dec_error,
                trigger_time=grb_alert.trigger_time_as_datetime,
                xml_payload=grb_alert.xml_string,
                thread_ts=grb_alert_db.thread_ts,
                reception_count=grb_alert_db.reception_count + 1,
            )
            self.gcn_stream.session_local.add(grb_alert_db_new)
            self.gcn_stream.session_local.commit()
            self.logger.info(
                f"GRB alert {grb_alert.trigger_id} already exists, "
                f"incrementing reception count to {grb_alert_db_new.reception_count}."
            )
            grb_alert_db = grb_alert_db_new

        return grb_alert_db

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
                    self.process_alert(notice=message.value(), topic=message.topic())
                    self.commit(message)
                except Exception as err:
                    self.logger.error(err)
                    raise err
