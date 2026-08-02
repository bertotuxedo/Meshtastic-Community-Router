from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable


@dataclass(frozen=True, slots=True)
class PacketReceivedEvent:
    topic: str
    payload: bytes
    qos: int
    retain: bool


PacketHandler = Callable[[PacketReceivedEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._packet_handlers: list[PacketHandler] = []
        self._lock = RLock()

    def subscribe_packets(
        self,
        handler: PacketHandler,
    ) -> None:
        with self._lock:
            self._packet_handlers.append(handler)

    def publish_packet(
        self,
        event: PacketReceivedEvent,
    ) -> None:
        with self._lock:
            handlers = list(self._packet_handlers)

        for handler in handlers:
            handler(event)
