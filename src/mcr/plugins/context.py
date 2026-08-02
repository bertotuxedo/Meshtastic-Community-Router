from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcr.broker import MqttBroker
from mcr.commands.registry import CommandRegistry
from mcr.database import RouterDatabase
from mcr.events import EventBus
from mcr.scheduler import Scheduler
from mcr.services.root_service import RootService


ReloadRootsFunction = Callable[[], None]
RootProviderFunction = Callable[[], list[str]]


@dataclass(slots=True)
class PluginContext:
    config: dict[str, Any]
    database: RouterDatabase
    broker: MqttBroker
    event_bus: EventBus
    command_registry: CommandRegistry
    scheduler: Scheduler
    root_service: RootService
    community_id: int
    root_provider: RootProviderFunction
    reload_roots: ReloadRootsFunction
