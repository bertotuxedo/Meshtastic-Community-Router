from __future__ import annotations

import logging
import threading
from typing import Any

from mcr.broker import MqttBroker
from mcr.config import env_bool
from mcr.database import RouterDatabase
from mcr.events import (
    EventBus,
    PacketReceivedEvent,
)
from mcr.packets import (
    decode_packet_identity,
    extract_root_and_suffix,
    is_community_encrypted_topic,
)


LOGGER = logging.getLogger("mcr.router")


class CommunityRouter:
    def __init__(
        self,
        config: dict[str, Any],
        database: RouterDatabase,
        broker: MqttBroker,
        event_bus: EventBus,
    ) -> None:
        self.config = config
        self.database = database
        self.broker = broker
        self.stop_event = threading.Event()

        routing_config = config["routing"]
        community_config = (
            config["communities"]["fats"]
        )
        bot_config = config.get("bot", {})

        self.routing_enabled = env_bool(
            "MCR_ROUTING_ENABLED",
            default=False,
        )

        self.bot_responses_enabled = env_bool(
            "MCR_BOT_RESPONSES_ENABLED",
            default=bool(
                bot_config.get("enabled", False)
            ),
        )

        self.bot_name = str(
            bot_config.get("name", "MCRBOT")
        ).strip() or "MCRBOT"

        self.community_key = "fats"

        self.display_name = str(
            community_config["display_name"]
        )

        self.channel_name = str(
            community_config["channel_name"]
        )

        self.community_id = (
            self.database.seed_community(
                community_key=self.community_key,
                display_name=self.display_name,
                channel_name=self.channel_name,
                rendezvous_root=str(
                    community_config[
                        "rendezvous_root"
                    ]
                ),
                initial_roots=list(
                    community_config.get(
                        "initial_roots",
                        [],
                    )
                ),
            )
        )

        self.roots: list[str] = []

        self.deduplication_seconds = int(
            routing_config.get(
                "deduplication_seconds",
                1800,
            )
        )

        self.root_reload_seconds = int(
            routing_config.get(
                "root_reload_seconds",
                10,
            )
        )

        event_bus.subscribe_packets(
            self.handle_packet
        )

    def bot_message(
        self,
        message: str,
    ) -> str:
        return f"{self.bot_name}: {message}"

    def desired_subscription_topics(
        self,
    ) -> set[str]:
        return {
            (
                f"{root}/2/e/"
                f"{self.channel_name}/#"
            )
            for root in self.roots
        }

    def reload_roots(self) -> None:
        current_roots = (
            self.database.get_enabled_roots(
                self.community_id
            )
        )

        if current_roots == self.roots:
            return

        previous_roots = set(self.roots)
        updated_roots = set(current_roots)

        added = sorted(
            updated_roots - previous_roots
        )

        removed = sorted(
            previous_roots - updated_roots
        )

        self.roots = current_roots

        if added:
            LOGGER.info(
                "Routing roots added: %s",
                ", ".join(added),
            )

        if removed:
            LOGGER.info(
                "Routing roots removed: %s",
                ", ".join(removed),
            )

        self.broker.set_subscriptions(
            self.desired_subscription_topics()
        )

    def root_reload_worker(self) -> None:
        while not self.stop_event.wait(
            self.root_reload_seconds
        ):
            try:
                self.reload_roots()
            except Exception:
                LOGGER.exception(
                    "Unable to reload routing roots"
                )

    def handle_packet(
        self,
        event: PacketReceivedEvent,
    ) -> None:
        parsed_topic = extract_root_and_suffix(
            event.topic,
            self.roots,
        )

        if parsed_topic is None:
            return

        source_root, suffix = parsed_topic

        if not is_community_encrypted_topic(
            suffix,
            self.channel_name,
        ):
            return

        (
            packet_key,
            packet_from,
            packet_id,
            decode_warning,
        ) = decode_packet_identity(
            event.payload
        )

        self.database.cleanup_packet_cache(
            self.deduplication_seconds
        )

        if self.database.packet_already_seen(
            packet_key
        ):
            self.database.record_duplicate_packet(
                community_id=self.community_id
            )

            LOGGER.info(
                "Duplicate ignored key=%s topic=%s",
                packet_key,
                event.topic,
            )
            return

        self.database.remember_packet(
            packet_key=packet_key,
            source_root=source_root,
            source_topic=event.topic,
        )

        self.database.touch_root(
            community_id=self.community_id,
            mqtt_root=source_root,
        )

        self.database.record_accepted_packet(
            community_id=self.community_id,
            node_number=packet_from,
            mqtt_root=source_root,
            channel_name=self.channel_name,
        )

        if decode_warning:
            LOGGER.warning(
                "Packet identity warning: %s",
                decode_warning,
            )

        LOGGER.info(
            "Accepted packet key=%s "
            "from=%s id=%s source=%s bytes=%s",
            packet_key,
            packet_from,
            packet_id,
            event.topic,
            len(event.payload),
        )

        if not self.routing_enabled:
            LOGGER.info(
                "Observer mode: routing disabled"
            )
            return

        for destination_root in self.roots:
            if destination_root == source_root:
                continue

            destination_topic = (
                f"{destination_root}/{suffix}"
            )

            if self.broker.publish(
                topic=destination_topic,
                payload=event.payload,
                qos=0,
                retain=False,
            ):
                self.database.record_routed_packet(
                    community_id=self.community_id,
                    mqtt_root=destination_root,
                    channel_name=self.channel_name,
                )

                LOGGER.info(
                    "Routed %s -> %s",
                    event.topic,
                    destination_topic,
                )

    def start(self) -> None:
        self.reload_roots()

        LOGGER.info(
            "Routing enabled=%s "
            "bot responses enabled=%s",
            self.routing_enabled,
            self.bot_responses_enabled,
        )

        LOGGER.info(
            "Bot identity=%s",
            self.bot_name,
        )

        LOGGER.info(
            "Database routing roots: %s",
            ", ".join(self.roots),
        )

        reload_thread = threading.Thread(
            target=self.root_reload_worker,
            name="root-reloader",
            daemon=True,
        )

        reload_thread.start()

    def stop(self) -> None:
        LOGGER.info("Stopping router")
        self.stop_event.set()
