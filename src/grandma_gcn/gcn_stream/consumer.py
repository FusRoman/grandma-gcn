from pathlib import Path
from gcn_kafka import Consumer as KafkaConsumer
import logging
import uuid

from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import build_gwalert_msg, new_alert_on_slack
from grandma_gcn.worker.gwemopt_worker import gwemopt_task


class Consumer(KafkaConsumer):
    def __init__(self, *, gcn_stream) -> None:
        self.logger = logging.getLogger("gcn_stream.consumer")
        self.logger.info("Starting GCN stream consumer")

        super().__init__(
            config=gcn_stream.gcn_config["KAFKA_CONFIG"],
            client_id=gcn_stream.gcn_config["CLIENT"]["id"],
            client_secret=gcn_stream.gcn_config["CLIENT"]["secret"],
        )

        self.gcn_stream = gcn_stream

        topics = gcn_stream.gcn_config["GCN_TOPICS"]["topics"]

        self.gw_alert_channel = gcn_stream.gcn_config["Slack"]["gw_alert_channel"]

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

    def process_alert(self, notice: bytes) -> None:
        """
        Process the alert and return a message.

        Parameters
        -----------
            notice (bytes): The alert notice in bytes.
        """
        self.logger.info("Processing alert")

        gw_alert = GW_alert(
            notice,
            BBH_threshold=self.gcn_stream.gcn_config["Threshold"]["BBH_proba"],
            Distance_threshold=self.gcn_stream.gcn_config["Threshold"]["Distance_cut"],
            ErrorRegion_threshold=self.gcn_stream.gcn_config["Threshold"][
                "Size_region_cut"
            ],
        )
        score, _, _ = gw_alert.gw_score()
        if score > 1:
            self.logger.info("Significant alert detected")

            path_notice = gw_alert.save_notice(self.gcn_stream.notice_path)

            new_alert_on_slack(
                gw_alert,
                build_gwalert_msg,
                self.gcn_stream.slack_client,
                channel=self.gw_alert_channel,
                logger=self.logger,
            )

            path_output_tiling = Path(
                f"{gw_alert.event_id}_gwemopt_tiling_{uuid.uuid4().hex}"
            )
            path_output_galaxy = Path(
                f"{gw_alert.event_id}_gwemopt_galaxy_{uuid.uuid4().hex}"
            )

            self.logger.info("Sending gwemopt task to celery worker")
            task_tiling = gwemopt_task.delay(
                self.gcn_stream.gcn_config["GWEMOPT"]["telescopes_tiling"],
                self.gcn_stream.gcn_config["GWEMOPT"]["tiling_nb_tiles"],
                self.gcn_stream.gcn_config["GWEMOPT"]["nside_flat"],
                self.gw_alert_channel,
                str(path_notice),
                str(path_output_tiling),
                self.gcn_stream.gcn_config["PATH"]["celery_task_log_path"],
                gw_alert.BBH_threshold,
                gw_alert.Distance_threshold,
                gw_alert.ErrorRegion_threshold,
                GW_alert.ObservationStrategy.TILING.name,
            )

            self.logger.info(
                f"Gwemopt launched for tiling telescopes with ID: {task_tiling.id}"
            )

            task_galaxy = gwemopt_task.delay(
                self.gcn_stream.gcn_config["GWEMOPT"]["telescopes_galaxy"],
                self.gcn_stream.gcn_config["GWEMOPT"]["nb_galaxies"],
                self.gcn_stream.gcn_config["GWEMOPT"]["nside_flat"],
                self.gw_alert_channel,
                str(path_notice),
                str(path_output_galaxy),
                self.gcn_stream.gcn_config["PATH"]["celery_task_log_path"],
                gw_alert.BBH_threshold,
                gw_alert.Distance_threshold,
                gw_alert.ErrorRegion_threshold,
                GW_alert.ObservationStrategy.GALAXYTARGETING.name,
            )

            self.logger.info(
                f"Gwemopt launched for galaxy targeting telescopes with ID: {task_galaxy.id}"
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
                    continue
