from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mcr.database import RouterDatabase


ReplyFunction = Callable[[str], bool]
ReloadRootsFunction = Callable[[], None]


@dataclass(slots=True)
class CommandContext:
    sender_node: int
    source_root: str
    argument: str
    bot_name: str
    community_id: int
    database: RouterDatabase
    reply: ReplyFunction
    reload_roots: ReloadRootsFunction
