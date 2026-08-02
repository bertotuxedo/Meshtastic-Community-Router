from __future__ import annotations

from mcr.commands.base import BotCommand
from mcr.commands.context import CommandContext


class StatusCommand(BotCommand):
    name = "!status"
    aliases = ("!stats",)
    description = "Show current router and community activity."

    def __init__(
        self,
        active_window_seconds: int = 900,
    ) -> None:
        self.active_window_seconds = (
            active_window_seconds
        )

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        activity = (
            context.database.get_activity_summary(
                community_id=context.community_id,
                active_window_seconds=(
                    self.active_window_seconds
                ),
            )
        )

        roots = (
            context.database.get_enabled_roots(
                context.community_id
            )
        )

        schema_version = (
            context.database.get_schema_version()
        )

        context.reply(
            "Online"
            f" | Hosts {activity['active_hosts']}"
            f" | Rooms {activity['active_rooms']}"
            f" | Roots {len(roots)}"
            f" | Accepted {activity['packets_accepted']}"
            f" | Routed {activity['packets_routed']}"
            f" | Schema {schema_version}"
        )
