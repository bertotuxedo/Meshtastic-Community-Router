from __future__ import annotations

from abc import ABC, abstractmethod

from mcr.commands.context import CommandContext


class BotCommand(ABC):
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""

    @abstractmethod
    def execute(
        self,
        context: CommandContext,
    ) -> None:
        raise NotImplementedError
