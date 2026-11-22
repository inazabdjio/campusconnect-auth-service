import json
from confluent_kafka import Producer


class KafkaEventPublisher:
    def __init__(
        self,
        enabled: bool,
        bootstrap_servers: str,
        user_registered_topic: str = "user.registered",
        user_deleted_topic: str = "user.deleted",
    ):
        self.enabled = enabled
        self.user_registered_topic = user_registered_topic
        self.user_deleted_topic = user_deleted_topic
        self._producer: Producer | None = None
        if self.enabled:
            self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    def publish(self, topic: str, key: str, payload: dict) -> None:
        if not self.enabled or not self._producer:
            return
        serialized = json.dumps(payload, default=str).encode("utf-8")
        self._producer.produce(topic=topic, key=key.encode("utf-8"), value=serialized)
        self._producer.flush(timeout=5.0)

    def publish_user_registered(self, payload: dict) -> None:
        self.publish(self.user_registered_topic, key=str(payload["userId"]), payload=payload)

    def publish_user_deleted(self, payload: dict) -> None:
        self.publish(self.user_deleted_topic, key=str(payload["userId"]), payload=payload)