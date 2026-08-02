from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from mcr.broker import MqttBroker
from mcr.commands.context import CommandContext
from mcr.commands.registry import CommandRegistry
from mcr.config import env_bool
from mcr.crypto import (
    create_text_service_envelope,
    decode_base64_psk,
    decrypt_service_envelope,
    parse_node_id,
)
from mcr.database import RouterDatabase
from mcr.events import (
    EventBus,
    PacketReceivedEvent,
)
from mcr.packets import (
    extract_root_and_suffix,
    is_community_encrypted_topic,
)


LOGGER = logging.getLogger("mcr.bot")


class CommunityBot:
    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus,
        broker: MqttBroker,
        database: RouterDatabase,
        community_id: int,
        root_provider: Callable[[], list[str]],
        reload_roots: Callable[[], None],
        command_registry: CommandRegistry | None = None,
    ) -> None:
        bot_config = config.get("bot", {})
        community_config = (
            config["communities"]["fats"]
        )

        self.broker = broker
        self.database = database
        self.community_id = community_id
        self.root_provider = root_provider
        self.reload_roots = reload_roots

        if command_registry is None:
            raise ValueError(
                "CommunityBot requires a command registry"
            )

        self.commands = command_registry

        self.enabled = env_bool(
            "MCR_BOT_RESPONSES_ENABLED",
            default=bool(
                bot_config.get("enabled", False)
            ),
        )

        self.name = str(
            bot_config.get("name", "MCRBOT")
        ).strip() or "MCRBOT"

        self.source_node = parse_node_id(
            str(bot_config["node_id"])
        )

        self.hop_limit = int(
            bot_config.get("hop_limit", 3)
        )

        self.channel_name = str(
            community_config["channel_name"]
        )

        self.rendezvous_root = str(
            community_config["rendezvous_root"]
        ).rstrip("/")

        self.psk = decode_base64_psk(
            os.environ["MCR_FATS_PSK_BASE64"]
        )

        self.processed_packets: dict[
            str,
            float,
        ] = {}

        self.processed_packets_lock = (
            threading.RLock()
        )

        self.deduplication_seconds = int(
            config.get("routing", {}).get(
                "deduplication_seconds",
                1800,
            )
        )

        event_bus.subscribe_packets(
            self.handle_packet
        )

        LOGGER.info(
            "Bot configured name=%s "
            "node=!%08x enabled=%s",
            self.name,
            self.source_node,
            self.enabled,
        )

    def format_message(
        self,
        message: str,
    ) -> str:
        return f"{self.name}: {message}"

    def current_roots(
        self,
    ) -> list[str]:
        return list(self.root_provider())

    def packet_key(
        self,
        source_node: int,
        packet_id: int,
    ) -> str:
        return f"mesh:{source_node}:{packet_id}"

    def packet_already_processed(
        self,
        packet_key: str,
    ) -> bool:
        now = time.monotonic()

        with self.processed_packets_lock:
            expired_keys = [
                key
                for key, timestamp
                in self.processed_packets.items()
                if (
                    now - timestamp
                    > self.deduplication_seconds
                )
            ]

            for key in expired_keys:
                self.processed_packets.pop(
                    key,
                    None,
                )

            if packet_key in self.processed_packets:
                return True

            self.processed_packets[packet_key] = now
            return False

    def send_text(
        self,
        message: str,
    ) -> bool:
        response_text = self.format_message(
            message
        )

        outbound = create_text_service_envelope(
            text=response_text,
            key=self.psk,
            channel_name=self.channel_name,
            source_node=self.source_node,
            hop_limit=self.hop_limit,
        )

        topic = (
            f"{self.rendezvous_root}/"
            f"{outbound.topic_suffix}"
        )

        published = self.broker.publish(
            topic=topic,
            payload=outbound.payload,
            qos=0,
            retain=False,
        )

        if published:
            LOGGER.info(
                "Published bot response "
                "id=%s topic=%s text=%r",
                outbound.packet_id,
                topic,
                response_text,
            )

        return published

    def build_context(
        self,
        sender_node: int,
        source_root: str,
        argument: str,
    ) -> CommandContext:
        return CommandContext(
            sender_node=sender_node,
            source_root=source_root,
            argument=argument,
            bot_name=self.name,
            community_id=self.community_id,
            database=self.database,
            reply=self.send_text,
            reload_roots=self.reload_roots,
        )

    def handle_packet(
        self,
        event: PacketReceivedEvent,
    ) -> None:
        parsed_topic = extract_root_and_suffix(
            event.topic,
            self.current_roots(),
        )

        if parsed_topic is None:
            return

        source_root, suffix = parsed_topic

        if not is_community_encrypted_topic(
            suffix,
            self.channel_name,
        ):
            return

        try:
            decoded = decrypt_service_envelope(
                payload=event.payload,
                key=self.psk,
            )
        except Exception as exc:
            LOGGER.debug(
                "Unable to decrypt topic=%s "
                "error=%s",
                event.topic,
                exc,
            )
            return

        packet_key = self.packet_key(
            source_node=decoded.source_node,
            packet_id=decoded.packet_id,
        )

        if self.packet_already_processed(
            packet_key
        ):
            return

        # Mark every packet on its first observed root before
        # deciding whether it is eligible for bot processing.
        # This prevents a command sent through another root
        # from being routed into msh/US/FATS and executed later.
        if source_root != self.rendezvous_root:
            LOGGER.debug(
                "Bot packet ignored outside "
                "rendezvous root key=%s "
                "source_root=%s",
                packet_key,
                source_root,
            )
            return

        if decoded.source_node == self.source_node:
            return

        if decoded.text is None:
            return

        text = decoded.text.strip()

        LOGGER.info(
            "Decoded FATS text "
            "from=!%08x id=%s text=%r",
            decoded.source_node,
            decoded.packet_id,
            text,
        )

        if not text.startswith("!"):
            return

        command_name, _, argument = (
            text.partition(" ")
        )

        command_name = command_name.casefold()
        argument = argument.strip()

        LOGGER.info(
            "Recognized command "
            "node=!%08x command=%s "
            "argument=%r",
            decoded.source_node,
            command_name,
            argument,
        )

        if not self.enabled:
            LOGGER.info(
                "Bot responses disabled; "
                "command was not answered"
            )
            return

        context = self.build_context(
            sender_node=decoded.source_node,
            source_root=source_root,
            argument=argument,
        )

        try:
            handled = self.commands.execute(
                command_name,
                context,
            )
        except Exception:
            LOGGER.exception(
                "Command failed "
                "node=!%08x command=%s",
                decoded.source_node,
                command_name,
            )

            self.send_text(
                "An internal error occurred "
                "while processing that command."
            )
            return

        if not handled:
            self.send_text(
                f"Unknown command {command_name}. "
                "Use !help."
            )
