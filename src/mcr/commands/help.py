from __future__ import annotations

from mcr.commands.base import BotCommand
from mcr.commands.context import CommandContext


class HelpCommand(BotCommand):
    name = "!help"
    aliases = ("!commands",)
    description = "Show available FATBOT commands."

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        context.reply(
            "Commands: !help, !register, !confirm, "
            "!topics, !mytopics, !unregister, !status"
        )
