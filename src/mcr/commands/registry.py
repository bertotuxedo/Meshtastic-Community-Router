from __future__ import annotations

import logging

from mcr.commands.base import BotCommand
from mcr.commands.context import CommandContext


LOGGER = logging.getLogger("mcr.commands")


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, BotCommand] = {}

    def register(
        self,
        command: BotCommand,
    ) -> None:
        names = (
            command.name,
            *command.aliases,
        )

        for name in names:
            normalized = self.normalize_name(name)

            if normalized in self._commands:
                raise ValueError(
                    f"Command already registered: {normalized}"
                )

            self._commands[normalized] = command

        LOGGER.info(
            "Registered command %s aliases=%s",
            command.name,
            command.aliases,
        )

    def resolve(
        self,
        name: str,
    ) -> BotCommand | None:
        return self._commands.get(
            self.normalize_name(name)
        )

    def execute(
        self,
        name: str,
        context: CommandContext,
    ) -> bool:
        command = self.resolve(name)

        if command is None:
            return False

        command.execute(context)
        return True

    def primary_commands(
        self,
    ) -> list[BotCommand]:
        unique: dict[str, BotCommand] = {}

        for command in self._commands.values():
            unique[command.name] = command

        return sorted(
            unique.values(),
            key=lambda command: command.name,
        )

    @staticmethod
    def normalize_name(
        name: str,
    ) -> str:
        normalized = name.strip().casefold()

        if not normalized.startswith("!"):
            normalized = f"!{normalized}"

        return normalized
