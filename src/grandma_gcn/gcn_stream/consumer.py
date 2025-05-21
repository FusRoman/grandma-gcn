from gcn_kafka import Consumer as KafkaConsumer
import logging

from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import new_gwalert_on_slack


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

    def process_alert(self, notice: bytes) -> str:
        """
        Process the alert and return a message.

        Parameters
        -----------
            notice (bytes): The alert notice in bytes.

        Returns
        -------
            str: The processed message.
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

            gw_alert.save_notice(self.gcn_stream.notice_path)

            new_gwalert_on_slack(
                gw_alert,
                self.gcn_stream.slack_client,
                channel=self.gw_alert_channel,
                logger=self.logger,
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
