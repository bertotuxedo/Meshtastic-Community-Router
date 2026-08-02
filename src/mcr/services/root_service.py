from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Callable

from mcr.config import normalize_root
from mcr.database import RouterDatabase


ReloadRootsFunction = Callable[[], None]


@dataclass(frozen=True, slots=True)
class RootRecord:
    mqtt_root: str
    enabled: bool
    system_root: bool
    registered_by: int | None
    created_at: int
    last_activity: int | None


@dataclass(frozen=True, slots=True)
class RootOperationResult:
    success: bool
    message: str
    mqtt_root: str | None = None
    confirmation_code: str | None = None


class RootService:
    def __init__(
        self,
        database: RouterDatabase,
        community_id: int,
        reload_roots: ReloadRootsFunction,
        maximum_roots: int = 100,
        maximum_roots_per_node: int = 3,
        confirmation_expiration_seconds: int = 300,
    ) -> None:
        self.database = database
        self.community_id = community_id
        self.reload_roots = reload_roots
        self.maximum_roots = maximum_roots
        self.maximum_roots_per_node = (
            maximum_roots_per_node
        )
        self.confirmation_expiration_seconds = (
            confirmation_expiration_seconds
        )

    @staticmethod
    def normalize_mqtt_root(
        value: str,
    ) -> str:
        return normalize_root(value)

    @staticmethod
    def validate_mqtt_root(
        value: str,
    ) -> RootOperationResult:
        root = normalize_root(value)

        if not root:
            return RootOperationResult(
                success=False,
                message="MQTT root cannot be empty.",
            )

        if len(root) > 128:
            return RootOperationResult(
                success=False,
                message="MQTT root is too long.",
                mqtt_root=root,
            )

        if not root.startswith("msh/"):
            return RootOperationResult(
                success=False,
                message="MQTT root must begin with msh/.",
                mqtt_root=root,
            )

        if "#" in root or "+" in root:
            return RootOperationResult(
                success=False,
                message=(
                    "MQTT root cannot contain "
                    "MQTT wildcards."
                ),
                mqtt_root=root,
            )

        if "//" in root:
            return RootOperationResult(
                success=False,
                message=(
                    "MQTT root cannot contain "
                    "empty levels."
                ),
                mqtt_root=root,
            )

        levels = root.split("/")

        if len(levels) < 3:
            return RootOperationResult(
                success=False,
                message=(
                    "MQTT root must contain at least "
                    "three levels, such as msh/US/CA."
                ),
                mqtt_root=root,
            )

        if any(
            not level.strip()
            for level in levels
        ):
            return RootOperationResult(
                success=False,
                message=(
                    "MQTT root contains an empty level."
                ),
                mqtt_root=root,
            )

        reserved_levels = {
            "2",
            "e",
            "json",
            "map",
        }

        if any(
            level.casefold() in reserved_levels
            for level in levels[1:]
        ):
            return RootOperationResult(
                success=False,
                message=(
                    "Enter only the MQTT root, not a "
                    "complete Meshtastic packet topic."
                ),
                mqtt_root=root,
            )

        allowed_characters = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "-_/"
        )

        if any(
            character not in allowed_characters
            for character in root
        ):
            return RootOperationResult(
                success=False,
                message=(
                    "MQTT root may contain only letters, "
                    "numbers, slashes, hyphens, and "
                    "underscores."
                ),
                mqtt_root=root,
            )

        return RootOperationResult(
            success=True,
            message="MQTT root is valid.",
            mqtt_root=root,
        )

    def list_enabled_roots(
        self,
    ) -> list[str]:
        return self.database.get_enabled_roots(
            self.community_id
        )

    def list_roots_registered_by(
        self,
        node_number: int,
    ) -> list[str]:
        rows = (
            self.database
            .get_roots_registered_by(
                community_id=self.community_id,
                node_number=node_number,
            )
        )

        return [
            str(row["mqtt_root"])
            for row in rows
        ]

    def root_exists(
        self,
        mqtt_root: str,
    ) -> bool:
        normalized = self.normalize_mqtt_root(
            mqtt_root
        )

        root = self.database.get_root(
            community_id=self.community_id,
            mqtt_root=normalized,
        )

        return (
            root is not None
            and bool(root["enabled"])
        )

    def count_enabled_roots(
        self,
    ) -> int:
        return len(
            self.list_enabled_roots()
        )

    def check_registration_limits(
        self,
        mqtt_root: str,
        node_number: int,
    ) -> RootOperationResult:
        if self.root_exists(mqtt_root):
            return RootOperationResult(
                success=False,
                message=(
                    f"{mqtt_root} is already registered."
                ),
                mqtt_root=mqtt_root,
            )

        if (
            self.count_enabled_roots()
            >= self.maximum_roots
        ):
            return RootOperationResult(
                success=False,
                message=(
                    "The community has reached its "
                    "maximum number of registered roots."
                ),
                mqtt_root=mqtt_root,
            )

        node_root_count = (
            self.database
            .count_roots_registered_by(
                community_id=self.community_id,
                node_number=node_number,
            )
        )

        if (
            node_root_count
            >= self.maximum_roots_per_node
        ):
            return RootOperationResult(
                success=False,
                message=(
                    "You have reached the maximum number "
                    "of roots allowed per node."
                ),
                mqtt_root=mqtt_root,
            )

        return RootOperationResult(
            success=True,
            message="Registration limits passed.",
            mqtt_root=mqtt_root,
        )

    def request_registration(
        self,
        mqtt_root: str,
        requested_by: int,
    ) -> RootOperationResult:
        validation = self.validate_mqtt_root(
            mqtt_root
        )

        if not validation.success:
            return validation

        normalized = validation.mqtt_root

        if normalized is None:
            return RootOperationResult(
                success=False,
                message=(
                    "Unable to normalize MQTT root."
                ),
            )

        limits = self.check_registration_limits(
            mqtt_root=normalized,
            node_number=requested_by,
        )

        if not limits.success:
            return limits

        self.database.upsert_node(
            node_number=requested_by
        )

        confirmation_code = (
            f"{secrets.randbelow(1_000_000):06d}"
        )

        expires_at = (
            int(time.time())
            + self.confirmation_expiration_seconds
        )

        self.database.create_pending_confirmation(
            community_id=self.community_id,
            node_number=requested_by,
            requested_root=normalized,
            confirmation_code=confirmation_code,
            expires_at=expires_at,
        )

        minutes = max(
            1,
            self.confirmation_expiration_seconds
            // 60,
        )

        return RootOperationResult(
            success=True,
            message=(
                f"Confirm {normalized} with "
                f"!confirm {confirmation_code} "
                f"within {minutes} minutes."
            ),
            mqtt_root=normalized,
            confirmation_code=confirmation_code,
        )

    def confirm_registration(
        self,
        confirmation_code: str,
        requested_by: int,
    ) -> RootOperationResult:
        code = confirmation_code.strip()

        if not code:
            return RootOperationResult(
                success=False,
                message=(
                    "Use !confirm followed by your "
                    "six-digit confirmation code."
                ),
            )

        self.database.cleanup_expired_confirmations()

        pending = (
            self.database
            .get_pending_confirmation(
                community_id=self.community_id,
                node_number=requested_by,
            )
        )

        if pending is None:
            return RootOperationResult(
                success=False,
                message=(
                    "No active registration request "
                    "was found for your node."
                ),
            )

        if str(
            pending["confirmation_code"]
        ) != code:
            return RootOperationResult(
                success=False,
                message=(
                    "That confirmation code is invalid."
                ),
            )

        if int(
            pending["expires_at"]
        ) <= int(time.time()):
            self.database.delete_pending_confirmation(
                community_id=self.community_id,
                node_number=requested_by,
            )

            return RootOperationResult(
                success=False,
                message=(
                    "That confirmation request expired. "
                    "Use !register again."
                ),
            )

        mqtt_root = str(
            pending["requested_root"]
        )

        limits = self.check_registration_limits(
            mqtt_root=mqtt_root,
            node_number=requested_by,
        )

        if not limits.success:
            self.database.delete_pending_confirmation(
                community_id=self.community_id,
                node_number=requested_by,
            )
            return limits

        self.database.add_root(
            community_id=self.community_id,
            mqtt_root=mqtt_root,
            registered_by=requested_by,
            system_root=False,
        )

        root = self.database.get_root(
            community_id=self.community_id,
            mqtt_root=mqtt_root,
        )

        if root is None:
            return RootOperationResult(
                success=False,
                message=(
                    "The root could not be loaded after "
                    "registration."
                ),
                mqtt_root=mqtt_root,
            )

        self.database.create_registration(
            community_id=self.community_id,
            node_number=requested_by,
            root_id=int(root["id"]),
        )

        self.database.delete_pending_confirmation(
            community_id=self.community_id,
            node_number=requested_by,
        )

        self.reload_roots()

        return RootOperationResult(
            success=True,
            message=(
                f"Registered {mqtt_root}. "
                "Routing is now active."
            ),
            mqtt_root=mqtt_root,
        )

    def register_root(
        self,
        mqtt_root: str,
        registered_by: int,
    ) -> RootOperationResult:
        validation = self.validate_mqtt_root(
            mqtt_root
        )

        if not validation.success:
            return validation

        normalized = validation.mqtt_root

        if normalized is None:
            return RootOperationResult(
                success=False,
                message=(
                    "Unable to normalize MQTT root."
                ),
            )

        limits = self.check_registration_limits(
            mqtt_root=normalized,
            node_number=registered_by,
        )

        if not limits.success:
            return limits

        self.database.upsert_node(
            node_number=registered_by
        )

        self.database.add_root(
            community_id=self.community_id,
            mqtt_root=normalized,
            registered_by=registered_by,
            system_root=False,
        )

        root = self.database.get_root(
            community_id=self.community_id,
            mqtt_root=normalized,
        )

        if root is not None:
            self.database.create_registration(
                community_id=self.community_id,
                node_number=registered_by,
                root_id=int(root["id"]),
            )

        self.reload_roots()

        return RootOperationResult(
            success=True,
            message=f"Registered {normalized}.",
            mqtt_root=normalized,
        )

    def unregister_root(
        self,
        mqtt_root: str,
        requested_by: int,
    ) -> RootOperationResult:
        validation = self.validate_mqtt_root(
            mqtt_root
        )

        if not validation.success:
            return validation

        normalized = validation.mqtt_root

        if normalized is None:
            return RootOperationResult(
                success=False,
                message=(
                    "Unable to normalize MQTT root."
                ),
            )

        root = self.database.get_root(
            community_id=self.community_id,
            mqtt_root=normalized,
        )

        if (
            root is None
            or not bool(root["enabled"])
        ):
            return RootOperationResult(
                success=False,
                message=(
                    f"{normalized} is not registered."
                ),
                mqtt_root=normalized,
            )

        if bool(root["system_root"]):
            return RootOperationResult(
                success=False,
                message=(
                    f"{normalized} is a protected "
                    "system root and cannot be removed."
                ),
                mqtt_root=normalized,
            )

        registered_by = root["registered_by"]

        if registered_by is None:
            return RootOperationResult(
                success=False,
                message=(
                    "This root has no registered owner "
                    "and cannot be removed by command."
                ),
                mqtt_root=normalized,
            )

        if int(registered_by) != requested_by:
            return RootOperationResult(
                success=False,
                message=(
                    "Only the node that registered this "
                    "root may remove it."
                ),
                mqtt_root=normalized,
            )

        root_id = int(root["id"])

        self.database.disable_root(
            community_id=self.community_id,
            mqtt_root=normalized,
        )

        self.database.deactivate_registration(
            community_id=self.community_id,
            node_number=requested_by,
            root_id=root_id,
        )

        self.reload_roots()

        return RootOperationResult(
            success=True,
            message=(
                f"Unregistered {normalized}. "
                "Routing is no longer active."
            ),
            mqtt_root=normalized,
        )
