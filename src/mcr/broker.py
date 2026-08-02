from __future__ import annotations

import logging
import os
from threading import Event, RLock
from typing import Any

import paho.mqtt.client as mqtt

from mcr.events import EventBus, PacketReceivedEvent


LOGGER = logging.getLogger("mcr.broker")


class MqttBroker:
    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus,
    ) -> None:
        mqtt_config = config["mqtt"]

        self.event_bus = event_bus

        self.host = os.environ["MCR_MQTT_HOST"]
        self.port = int(
            os.getenv("MCR_MQTT_PORT", "1883")
        )
        self.username = os.environ[
            "MCR_MQTT_USERNAME"
        ]
        self.password = os.environ[
            "MCR_MQTT_PASSWORD"
        ]

        self.client_id = str(
            mqtt_config.get(
                "client_id",
                "mcr-fats-router",
            )
        )
        self.keepalive = int(
            mqtt_config.get("keepalive", 60)
        )

        self.connected = Event()
        self.subscription_lock = RLock()

        self.desired_topics: set[str] = set()
        self.active_topics: set[str] = set()

        self.client = mqtt.Client(
            callback_api_version=(
                mqtt.CallbackAPIVersion.VERSION2
            ),
            client_id=self.client_id,
            protocol=mqtt.MQTTv311,
        )

        self.client.username_pw_set(
            self.username,
            self.password,
        )

        self.client.reconnect_delay_set(
            min_delay=int(
                mqtt_config.get(
                    "reconnect_min_seconds",
                    2,
                )
            ),
            max_delay=int(
                mqtt_config.get(
                    "reconnect_max_seconds",
                    60,
                )
            ),
        )

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = (
            self.on_disconnect
        )
        self.client.on_message = self.on_message
        self.client.on_subscribe = (
            self.on_subscribe
        )
        self.client.on_unsubscribe = (
            self.on_unsubscribe
        )

    def set_subscriptions(
        self,
        topics: set[str],
    ) -> None:
        with self.subscription_lock:
            self.desired_topics = set(topics)

        if self.connected.is_set():
            self.synchronize_subscriptions()

    def synchronize_subscriptions(self) -> None:
        with self.subscription_lock:
            topics_to_remove = (
                self.active_topics
                - self.desired_topics
            )
            topics_to_add = (
                self.desired_topics
                - self.active_topics
            )

            for topic in sorted(topics_to_remove):
                result, message_id = (
                    self.client.unsubscribe(topic)
                )

                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.active_topics.discard(topic)
                    LOGGER.info(
                        "Requested unsubscribe: "
                        "%s mid=%s",
                        topic,
                        message_id,
                    )
                else:
                    LOGGER.error(
                        "Unable to unsubscribe "
                        "from %s: %s",
                        topic,
                        result,
                    )

            for topic in sorted(topics_to_add):
                result, message_id = (
                    self.client.subscribe(
                        topic,
                        qos=0,
                    )
                )

                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.active_topics.add(topic)
                    LOGGER.info(
                        "Requested subscription: "
                        "%s mid=%s",
                        topic,
                        message_id,
                    )
                else:
                    LOGGER.error(
                        "Unable to subscribe "
                        "to %s: %s",
                        topic,
                        result,
                    )

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        result = self.client.publish(
            topic,
            payload=payload,
            qos=qos,
            retain=retain,
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            LOGGER.error(
                "Publish failed rc=%s topic=%s",
                result.rc,
                topic,
            )
            return False

        return True

    def on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            LOGGER.error(
                "MQTT connection rejected: %s",
                reason_code,
            )
            return

        LOGGER.info(
            "Connected to %s:%s as %s",
            self.host,
            self.port,
            self.client_id,
        )

        self.connected.set()

        with self.subscription_lock:
            self.active_topics.clear()

        self.synchronize_subscriptions()

    def on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        self.connected.clear()

        with self.subscription_lock:
            self.active_topics.clear()

        if reason_code == 0:
            LOGGER.info(
                "Disconnected cleanly"
            )
        else:
            LOGGER.warning(
                "Unexpected MQTT "
                "disconnection: %s",
                reason_code,
            )

    def on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        self.event_bus.publish_packet(
            PacketReceivedEvent(
                topic=message.topic,
                payload=bytes(message.payload),
                qos=int(message.qos),
                retain=bool(message.retain),
            )
        )

    def on_subscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        message_id: int,
        reason_codes: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        LOGGER.info(
            "Subscription acknowledged: "
            "mid=%s reasons=%s",
            message_id,
            reason_codes,
        )

    def on_unsubscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        message_id: int,
        reason_codes: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        LOGGER.info(
            "Unsubscribe acknowledged: "
            "mid=%s reasons=%s",
            message_id,
            reason_codes,
        )

    def run(self) -> None:
        self.client.connect(
            self.host,
            self.port,
            keepalive=self.keepalive,
        )

        self.client.loop_forever(
            retry_first_connection=True
        )

    def stop(self) -> None:
        self.client.disconnect()
