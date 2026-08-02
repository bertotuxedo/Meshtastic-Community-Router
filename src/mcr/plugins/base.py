from __future__ import annotations

from abc import ABC
from typing import ClassVar

from mcr.plugins.context import PluginContext


class Plugin(ABC):
    name: ClassVar[str]
    version: ClassVar[str] = "0.1.0"
    description: ClassVar[str] = ""

    def startup(
        self,
        context: PluginContext,
    ) -> None:
        """
        Called once during application startup.

        Plugins should register commands, subscribe to
        events, initialize state, or start workers here.
        """

    def shutdown(self) -> None:
        """
        Called when the application is shutting down.
        """

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "healthy": True,
        }
