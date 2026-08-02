from __future__ import annotations

from mcr.commands.base import BotCommand
from mcr.commands.context import CommandContext
from mcr.services.root_service import RootService


def format_root_list(
    heading: str,
    roots: list[str],
) -> str:
    if not roots:
        return f"{heading}: none."

    return (
        f"{heading} ({len(roots)}): "
        f"{', '.join(roots)}"
    )


class TopicsCommand(BotCommand):
    name = "!topics"
    aliases = ("!roots",)
    description = (
        "List all active community MQTT roots."
    )

    def __init__(
        self,
        root_service: RootService,
    ) -> None:
        self.root_service = root_service

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        roots = (
            self.root_service
            .list_enabled_roots()
        )

        context.reply(
            format_root_list(
                heading="Active roots",
                roots=roots,
            )
        )


class MyTopicsCommand(BotCommand):
    name = "!mytopics"
    aliases = ("!myroots",)
    description = (
        "List MQTT roots registered by your node."
    )

    def __init__(
        self,
        root_service: RootService,
    ) -> None:
        self.root_service = root_service

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        roots = (
            self.root_service
            .list_roots_registered_by(
                context.sender_node
            )
        )

        if not roots:
            context.reply(
                "You have no registered roots."
            )
            return

        context.reply(
            format_root_list(
                heading="Your roots",
                roots=roots,
            )
        )


class RegisterCommand(BotCommand):
    name = "!register"
    aliases = ("!join",)
    description = (
        "Request registration of an MQTT root."
    )

    def __init__(
        self,
        root_service: RootService,
    ) -> None:
        self.root_service = root_service

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        if not context.argument:
            context.reply(
                "Usage: !register msh/US/CA"
            )
            return

        result = (
            self.root_service
            .request_registration(
                mqtt_root=context.argument,
                requested_by=(
                    context.sender_node
                ),
            )
        )

        context.reply(result.message)


class ConfirmCommand(BotCommand):
    name = "!confirm"
    aliases = ()
    description = (
        "Confirm a pending root registration."
    )

    def __init__(
        self,
        root_service: RootService,
    ) -> None:
        self.root_service = root_service

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        result = (
            self.root_service
            .confirm_registration(
                confirmation_code=(
                    context.argument
                ),
                requested_by=(
                    context.sender_node
                ),
            )
        )

        context.reply(result.message)


class UnregisterCommand(BotCommand):
    name = "!unregister"
    aliases = ("!leave",)
    description = (
        "Remove an MQTT root registered "
        "by your node."
    )

    def __init__(
        self,
        root_service: RootService,
    ) -> None:
        self.root_service = root_service

    def execute(
        self,
        context: CommandContext,
    ) -> None:
        if not context.argument:
            context.reply(
                "Usage: !unregister msh/US/CA"
            )
            return

        result = (
            self.root_service
            .unregister_root(
                mqtt_root=context.argument,
                requested_by=(
                    context.sender_node
                ),
            )
        )

        context.reply(result.message)
