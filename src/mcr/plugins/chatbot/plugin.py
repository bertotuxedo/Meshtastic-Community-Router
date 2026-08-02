from __future__ import annotations

import logging

from mcr.commands.help import HelpCommand
from mcr.commands.status import StatusCommand
from mcr.plugins.base import Plugin
from mcr.plugins.context import PluginContext


LOGGER = logging.getLogger(
    "mcr.plugins.chatbot"
)


class ChatbotPlugin(Plugin):
    name = "chatbot"
    version = "0.2.0"
    description = (
        "Core FATBOT conversational commands."
    )

    def __init__(self) -> None:
        self.started = False

    def startup(
        self,
        context: PluginContext,
    ) -> None:
        activity_config = (
            context.config.get("activity")
            or {}
        )

        active_window_seconds = int(
            activity_config.get(
                "active_window_seconds",
                900,
            )
        )

        context.command_registry.register(
            HelpCommand()
        )

        context.command_registry.register(
            StatusCommand(
                active_window_seconds=(
                    active_window_seconds
                )
            )
        )

        self.started = True

        LOGGER.info(
            "Chatbot commands registered"
        )

    def shutdown(self) -> None:
        self.started = False

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "healthy": self.started,
            "commands": [
                "!help",
                "!status",
            ],
        }
