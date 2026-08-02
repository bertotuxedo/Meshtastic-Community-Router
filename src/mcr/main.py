from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from typing import Any

from mcr.api import StatusApi
from mcr.bot import CommunityBot
from mcr.broker import MqttBroker
from mcr.commands.registry import CommandRegistry
from mcr.config import load_config
from mcr.database import RouterDatabase
from mcr.events import EventBus
from mcr.plugins.chatbot import ChatbotPlugin
from mcr.plugins.context import PluginContext
from mcr.plugins.manager import PluginManager
from mcr.plugins.registration import (
    RegistrationPlugin,
)
from mcr.router import CommunityRouter
from mcr.scheduler import Scheduler
from mcr.services.root_service import RootService


LOGGER = logging.getLogger("mcr")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Meshtastic Community Router"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML configuration file.",
    )

    arguments = parser.parse_args()
    config = load_config(arguments.config)

    log_level_name = (
        config.get("application", {})
        .get("log_level", "INFO")
        .upper()
    )

    logging.basicConfig(
        level=getattr(
            logging,
            log_level_name,
            logging.INFO,
        ),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    application_started_at = time.time()

    database_path = os.getenv(
        "MCR_DATABASE",
        "/data/router.db",
    )

    database = RouterDatabase(
        database_path
    )

    event_bus = EventBus()
    command_registry = CommandRegistry()

    scheduler_config = config.get(
        "scheduler",
        {},
    )

    scheduler = Scheduler(
        poll_interval_seconds=float(
            scheduler_config.get(
                "poll_interval_seconds",
                1.0,
            )
        )
    )

    broker = MqttBroker(
        config=config,
        event_bus=event_bus,
    )

    router = CommunityRouter(
        config=config,
        database=database,
        broker=broker,
        event_bus=event_bus,
    )

    routing_config = config.get(
        "routing",
        {},
    )

    registration_config = config.get(
        "registration",
        {},
    )

    root_service = RootService(
        database=database,
        community_id=router.community_id,
        reload_roots=router.reload_roots,
        maximum_roots=int(
            routing_config.get(
                "maximum_registered_roots",
                100,
            )
        ),
        maximum_roots_per_node=int(
            registration_config.get(
                "maximum_roots_per_node",
                3,
            )
        ),
        confirmation_expiration_seconds=int(
            registration_config.get(
                "confirmation_expiration_seconds",
                300,
            )
        ),
    )

    plugin_context = PluginContext(
        config=config,
        database=database,
        broker=broker,
        event_bus=event_bus,
        command_registry=command_registry,
        scheduler=scheduler,
        root_service=root_service,
        community_id=router.community_id,
        root_provider=lambda: list(
            router.roots
        ),
        reload_roots=router.reload_roots,
    )

    plugin_manager = PluginManager(
        context=plugin_context
    )

    plugin_manager.register(
        ChatbotPlugin()
    )

    plugin_manager.register(
        RegistrationPlugin()
    )

    plugin_manager.startup()
    scheduler.start()

    bot = CommunityBot(
        config=config,
        event_bus=event_bus,
        broker=broker,
        database=database,
        community_id=router.community_id,
        root_provider=lambda: list(
            router.roots
        ),
        reload_roots=router.reload_roots,
        command_registry=command_registry,
    )

    api_config = config.get(
        "api",
        {},
    )

    api_enabled = bool(
        api_config.get(
            "enabled",
            True,
        )
    )

    api_host = str(
        api_config.get(
            "host",
            "0.0.0.0",
        )
    )

    api_port = int(
        api_config.get(
            "port",
            8080,
        )
    )

    activity_config = (
        config.get("activity")
        or {}
    )

    active_window_seconds = int(
        activity_config.get(
            "active_window_seconds",
            900,
        )
    )

    def build_status() -> dict[str, Any]:
        roots = (
            root_service.list_enabled_roots()
        )

        activity = (
            database.get_activity_summary(
                community_id=router.community_id,
                active_window_seconds=(
                    active_window_seconds
                ),
            )
        )

        active_nodes = (
            database.get_active_nodes(
                community_id=router.community_id,
                active_window_seconds=(
                    active_window_seconds
                ),
            )
        )

        active_rooms = (
            database.get_active_rooms(
                community_id=router.community_id,
                active_window_seconds=(
                    active_window_seconds
                ),
            )
        )

        return {
            "name": (
                "Meshtastic Community Router"
            ),
            "status": "running",
            "read_only_api": True,
            "uptime_seconds": int(
                time.time()
                - application_started_at
            ),
            "database": {
                "path": database_path,
                "schema_version": (
                    database.get_schema_version()
                ),
            },
            "routing": {
                "enabled": (
                    router.routing_enabled
                ),
                "community_id": (
                    router.community_id
                ),
                "community_key": (
                    router.community_key
                ),
                "channel_name": (
                    router.channel_name
                ),
            },
            "roots": roots,
            "root_count": len(roots),
            "activity": activity,
            "active_nodes": active_nodes,
            "active_rooms": active_rooms,
            "plugins": (
                plugin_manager.health()
            ),
            "scheduler": (
                scheduler.health()
            ),
            "bot": {
                "name": bot.name,
                "enabled": bot.enabled,
                "node_id": (
                    f"!{bot.source_node:08x}"
                ),
            },
        }

    status_api = StatusApi(
        host=api_host,
        port=api_port,
        status_provider=build_status,
    )

    if api_enabled:
        status_api.start()

    shutting_down = False

    def stop_handler(
        signum: int,
        frame: Any,
    ) -> None:
        nonlocal shutting_down

        if shutting_down:
            return

        shutting_down = True

        LOGGER.info(
            "Received signal %s",
            signum,
        )

        status_api.stop()
        scheduler.stop()
        plugin_manager.shutdown()
        router.stop()
        broker.stop()

    signal.signal(
        signal.SIGTERM,
        stop_handler,
    )

    signal.signal(
        signal.SIGINT,
        stop_handler,
    )

    try:
        router.start()
        broker.run()
    except Exception:
        LOGGER.exception(
            "Application stopped due to an error"
        )
        return 1
    finally:
        if not shutting_down:
            status_api.stop()
            scheduler.stop()
            plugin_manager.shutdown()

        database.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
