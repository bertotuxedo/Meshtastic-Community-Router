from __future__ import annotations

import logging
from threading import RLock

from mcr.plugins.base import Plugin
from mcr.plugins.context import PluginContext


LOGGER = logging.getLogger("mcr.plugins")


class PluginManager:
    def __init__(
        self,
        context: PluginContext,
    ) -> None:
        self.context = context
        self.plugins: dict[str, Plugin] = {}
        self.started_plugins: list[str] = []
        self.lock = RLock()

    def register(
        self,
        plugin: Plugin,
    ) -> None:
        name = plugin.name.strip().casefold()

        if not name:
            raise ValueError(
                "Plugin name cannot be empty"
            )

        with self.lock:
            if name in self.plugins:
                raise ValueError(
                    f"Plugin already registered: {name}"
                )

            self.plugins[name] = plugin

        LOGGER.info(
            "Registered plugin name=%s version=%s",
            plugin.name,
            plugin.version,
        )

    def startup(self) -> None:
        with self.lock:
            plugins = list(self.plugins.items())

        for name, plugin in plugins:
            LOGGER.info(
                "Starting plugin %s",
                plugin.name,
            )

            try:
                plugin.startup(self.context)
            except Exception:
                LOGGER.exception(
                    "Plugin failed during startup: %s",
                    plugin.name,
                )
                raise

            self.started_plugins.append(name)

            LOGGER.info(
                "Plugin started: %s",
                plugin.name,
            )

    def shutdown(self) -> None:
        for name in reversed(
            self.started_plugins
        ):
            plugin = self.plugins.get(name)

            if plugin is None:
                continue

            LOGGER.info(
                "Stopping plugin %s",
                plugin.name,
            )

            try:
                plugin.shutdown()
            except Exception:
                LOGGER.exception(
                    "Plugin failed during shutdown: %s",
                    plugin.name,
                )

        self.started_plugins.clear()

    def health(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []

        with self.lock:
            plugins = list(self.plugins.values())

        for plugin in plugins:
            try:
                results.append(plugin.health())
            except Exception as exc:
                results.append(
                    {
                        "name": plugin.name,
                        "version": plugin.version,
                        "healthy": False,
                        "error": str(exc),
                    }
                )

        return results
