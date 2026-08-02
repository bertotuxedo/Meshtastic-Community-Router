from __future__ import annotations

import logging

from mcr.plugins.base import Plugin
from mcr.plugins.context import PluginContext
from mcr.plugins.registration.commands import (
    ConfirmCommand,
    MyTopicsCommand,
    RegisterCommand,
    TopicsCommand,
    UnregisterCommand,
)


LOGGER = logging.getLogger(
    "mcr.plugins.registration"
)


class RegistrationPlugin(Plugin):
    name = "registration"
    version = "0.4.0"
    description = (
        "Community MQTT root registration "
        "and discovery commands."
    )

    cleanup_job_name = (
        "registration.cleanup_expired_confirmations"
    )

    def __init__(self) -> None:
        self.started = False
        self.context: PluginContext | None = None
        self.cleanup_interval_seconds = 60

    def startup(
        self,
        context: PluginContext,
    ) -> None:
        self.context = context

        registration_config = context.config.get(
            "registration",
            {},
        )

        self.cleanup_interval_seconds = int(
            registration_config.get(
                "cleanup_interval_seconds",
                60,
            )
        )

        commands = [
            TopicsCommand(
                root_service=context.root_service
            ),
            MyTopicsCommand(
                root_service=context.root_service
            ),
            RegisterCommand(
                root_service=context.root_service
            ),
            ConfirmCommand(
                root_service=context.root_service
            ),
            UnregisterCommand(
                root_service=context.root_service
            ),
        ]

        for command in commands:
            context.command_registry.register(
                command
            )

        context.scheduler.register_interval(
            name=self.cleanup_job_name,
            interval_seconds=(
                self.cleanup_interval_seconds
            ),
            function=self.cleanup_expired_confirmations,
            run_immediately=True,
        )

        self.started = True

        LOGGER.info(
            "Registration commands and cleanup "
            "job registered"
        )

    def cleanup_expired_confirmations(
        self,
    ) -> None:
        if self.context is None:
            return

        deleted = (
            self.context.database
            .cleanup_expired_confirmations()
        )

        if deleted > 0:
            LOGGER.info(
                "Deleted %s expired registration "
                "confirmation(s)",
                deleted,
            )

    def shutdown(self) -> None:
        if self.context is not None:
            self.context.scheduler.unregister(
                self.cleanup_job_name
            )

        self.context = None
        self.started = False

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "healthy": self.started,
            "cleanup_interval_seconds": (
                self.cleanup_interval_seconds
            ),
            "commands": [
                "!topics",
                "!mytopics",
                "!register",
                "!confirm",
                "!unregister",
            ],
        }
