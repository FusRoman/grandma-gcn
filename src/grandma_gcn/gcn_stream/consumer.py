from gcn_kafka import Consumer as KafkaConsumer
import logging

logger = logging.getLogger(__name__)


class Consumer(KafkaConsumer):
    def __init__(self, *, gcn_stream) -> None:
        super().__init__(
            config=gcn_stream.kafka_config,
            client_id=gcn_stream.gcn_config["CLIENT"]["client_id"],
            client_secret=gcn_stream.gcn_config["CLIENT"]["client_secret"],
        )

        self.gcn_stream = gcn_stream

        topics = list(gcn_stream.topics.keys())

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

                logger.info("-- A new notice has arrived --")
                logger.info(f"topic: {message.topic()}")
                logger.info(f"current offset: {message.offset()}")
                if message.error():
                    logger.error(message.error())
                    continue
                try:
                    logger.info(f"message: {message.value()}")
                    self.commit(message)
                except Exception as err:
                    logger.error(err)
                    continue
