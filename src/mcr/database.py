from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from mcr.config import normalize_root
from mcr.migrations import MigrationRunner


class RouterDatabase:
    def __init__(
        self,
        database_path: str,
    ) -> None:
        path = Path(database_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            path,
            check_same_thread=False,
        )

        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()

        self.configure_connection()
        self.run_migrations()

    def configure_connection(self) -> None:
        with self.lock:
            self.connection.execute(
                "PRAGMA foreign_keys = ON"
            )

            self.connection.execute(
                "PRAGMA busy_timeout = 5000"
            )

            self.connection.commit()

    def run_migrations(self) -> None:
        with self.lock:
            runner = MigrationRunner(
                connection=self.connection
            )

            runner.run()

    def seed_community(
        self,
        community_key: str,
        display_name: str,
        channel_name: str,
        rendezvous_root: str,
        initial_roots: list[str],
    ) -> int:
        now = int(time.time())

        rendezvous_root = normalize_root(
            rendezvous_root
        )

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO communities (
                    community_key,
                    display_name,
                    channel_name,
                    rendezvous_root,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(community_key)
                DO UPDATE SET
                    display_name = excluded.display_name,
                    channel_name = excluded.channel_name,
                    rendezvous_root = excluded.rendezvous_root
                """,
                (
                    community_key,
                    display_name,
                    channel_name,
                    rendezvous_root,
                    now,
                ),
            )

            row = self.connection.execute(
                """
                SELECT id
                FROM communities
                WHERE community_key = ?
                """,
                (community_key,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Unable to create community "
                    f"{community_key}"
                )

            community_id = int(
                row["id"]
            )

            seeded_roots = {
                rendezvous_root,
                *[
                    normalize_root(root)
                    for root in initial_roots
                ],
            }

            for root in seeded_roots:
                self.connection.execute(
                    """
                    INSERT INTO roots (
                        community_id,
                        mqtt_root,
                        enabled,
                        system_root,
                        created_at
                    )
                    VALUES (?, ?, 1, 1, ?)
                    ON CONFLICT(
                        community_id,
                        mqtt_root
                    )
                    DO UPDATE SET
                        enabled = 1,
                        system_root = 1
                    """,
                    (
                        community_id,
                        root,
                        now,
                    ),
                )

            self.connection.commit()

            return community_id

    def get_enabled_roots(
        self,
        community_id: int,
    ) -> list[str]:
        with self.lock:
            rows = self.connection.execute(
                """
                SELECT mqtt_root
                FROM roots
                WHERE community_id = ?
                  AND enabled = 1
                ORDER BY mqtt_root
                """,
                (community_id,),
            ).fetchall()

        return [
            str(row["mqtt_root"])
            for row in rows
        ]

    def add_root(
        self,
        community_id: int,
        mqtt_root: str,
        registered_by: int | None = None,
        system_root: bool = False,
    ) -> None:
        now = int(time.time())

        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO roots (
                    community_id,
                    mqtt_root,
                    enabled,
                    system_root,
                    registered_by,
                    created_at,
                    last_activity
                )
                VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(
                    community_id,
                    mqtt_root
                )
                DO UPDATE SET
                    enabled = 1,
                    registered_by = COALESCE(
                        excluded.registered_by,
                        roots.registered_by
                    )
                """,
                (
                    community_id,
                    mqtt_root,
                    1 if system_root else 0,
                    registered_by,
                    now,
                    now,
                ),
            )

            self.connection.commit()

    def disable_root(
        self,
        community_id: int,
        mqtt_root: str,
    ) -> None:
        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            self.connection.execute(
                """
                UPDATE roots
                SET enabled = 0
                WHERE community_id = ?
                  AND mqtt_root = ?
                  AND system_root = 0
                """,
                (
                    community_id,
                    mqtt_root,
                ),
            )

            self.connection.commit()

    def touch_root(
        self,
        community_id: int,
        mqtt_root: str,
    ) -> None:
        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            self.connection.execute(
                """
                UPDATE roots
                SET last_activity = ?
                WHERE community_id = ?
                  AND mqtt_root = ?
                """,
                (
                    int(time.time()),
                    community_id,
                    mqtt_root,
                ),
            )

            self.connection.commit()

    def upsert_node(
        self,
        node_number: int,
    ) -> None:
        now = int(time.time())

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO nodes (
                    node_number,
                    first_seen,
                    last_seen
                )
                VALUES (?, ?, ?)
                ON CONFLICT(node_number)
                DO UPDATE SET
                    last_seen = excluded.last_seen
                """,
                (
                    node_number,
                    now,
                    now,
                ),
            )

            self.connection.commit()

    def get_root(
        self,
        community_id: int,
        mqtt_root: str,
    ) -> sqlite3.Row | None:
        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            return self.connection.execute(
                """
                SELECT
                    id,
                    community_id,
                    mqtt_root,
                    enabled,
                    system_root,
                    registered_by,
                    created_at,
                    last_activity
                FROM roots
                WHERE community_id = ?
                  AND mqtt_root = ?
                """,
                (
                    community_id,
                    mqtt_root,
                ),
            ).fetchone()

    def count_roots_registered_by(
        self,
        community_id: int,
        node_number: int,
    ) -> int:
        with self.lock:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS root_count
                FROM roots
                WHERE community_id = ?
                  AND registered_by = ?
                  AND enabled = 1
                  AND system_root = 0
                """,
                (
                    community_id,
                    node_number,
                ),
            ).fetchone()

        if row is None:
            return 0

        return int(
            row["root_count"]
        )

    def get_roots_registered_by(
        self,
        community_id: int,
        node_number: int,
    ) -> list[sqlite3.Row]:
        with self.lock:
            rows = self.connection.execute(
                """
                SELECT
                    id,
                    community_id,
                    mqtt_root,
                    enabled,
                    system_root,
                    registered_by,
                    created_at,
                    last_activity
                FROM roots
                WHERE community_id = ?
                  AND registered_by = ?
                  AND enabled = 1
                  AND system_root = 0
                ORDER BY mqtt_root
                """,
                (
                    community_id,
                    node_number,
                ),
            ).fetchall()

        return list(rows)

    def create_pending_confirmation(
        self,
        community_id: int,
        node_number: int,
        requested_root: str,
        confirmation_code: str,
        expires_at: int,
    ) -> None:
        now = int(time.time())

        requested_root = normalize_root(
            requested_root
        )

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO pending_confirmations (
                    community_id,
                    node_number,
                    requested_root,
                    confirmation_code,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    community_id,
                    node_number
                )
                DO UPDATE SET
                    requested_root = excluded.requested_root,
                    confirmation_code = excluded.confirmation_code,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    community_id,
                    node_number,
                    requested_root,
                    confirmation_code,
                    now,
                    expires_at,
                ),
            )

            self.connection.commit()

    def get_pending_confirmation(
        self,
        community_id: int,
        node_number: int,
    ) -> sqlite3.Row | None:
        with self.lock:
            return self.connection.execute(
                """
                SELECT
                    id,
                    community_id,
                    node_number,
                    requested_root,
                    confirmation_code,
                    created_at,
                    expires_at
                FROM pending_confirmations
                WHERE community_id = ?
                  AND node_number = ?
                """,
                (
                    community_id,
                    node_number,
                ),
            ).fetchone()

    def delete_pending_confirmation(
        self,
        community_id: int,
        node_number: int,
    ) -> None:
        with self.lock:
            self.connection.execute(
                """
                DELETE FROM pending_confirmations
                WHERE community_id = ?
                  AND node_number = ?
                """,
                (
                    community_id,
                    node_number,
                ),
            )

            self.connection.commit()

    def cleanup_expired_confirmations(
        self,
    ) -> int:
        now = int(time.time())

        with self.lock:
            cursor = self.connection.execute(
                """
                DELETE FROM pending_confirmations
                WHERE expires_at <= ?
                """,
                (now,),
            )

            self.connection.commit()

        return int(
            cursor.rowcount
        )

    def create_registration(
        self,
        community_id: int,
        node_number: int,
        root_id: int,
    ) -> None:
        now = int(time.time())

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO registrations (
                    community_id,
                    node_number,
                    root_id,
                    created_at,
                    active
                )
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(
                    community_id,
                    node_number,
                    root_id
                )
                DO UPDATE SET
                    active = 1
                """,
                (
                    community_id,
                    node_number,
                    root_id,
                    now,
                ),
            )

            self.connection.commit()

    def deactivate_registration(
        self,
        community_id: int,
        node_number: int,
        root_id: int,
    ) -> None:
        with self.lock:
            self.connection.execute(
                """
                UPDATE registrations
                SET active = 0
                WHERE community_id = ?
                  AND node_number = ?
                  AND root_id = ?
                """,
                (
                    community_id,
                    node_number,
                    root_id,
                ),
            )

            self.connection.commit()

    def packet_already_seen(
        self,
        packet_key: str,
    ) -> bool:
        with self.lock:
            row = self.connection.execute(
                """
                SELECT 1
                FROM routed_packets
                WHERE packet_key = ?
                """,
                (packet_key,),
            ).fetchone()

        return row is not None

    def remember_packet(
        self,
        packet_key: str,
        source_root: str,
        source_topic: str,
    ) -> None:
        with self.lock:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO routed_packets (
                    packet_key,
                    source_root,
                    source_topic,
                    first_seen
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    packet_key,
                    source_root,
                    source_topic,
                    int(time.time()),
                ),
            )

            self.connection.commit()

    def cleanup_packet_cache(
        self,
        deduplication_seconds: int,
    ) -> None:
        cutoff = (
            int(time.time())
            - deduplication_seconds
        )

        with self.lock:
            self.connection.execute(
                """
                DELETE FROM routed_packets
                WHERE first_seen < ?
                """,
                (cutoff,),
            )

            self.connection.commit()

    def record_accepted_packet(
        self,
        community_id: int,
        node_number: int | None,
        mqtt_root: str,
        channel_name: str,
    ) -> None:
        now = int(time.time())

        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            if (
                node_number is not None
                and node_number > 0
            ):
                self.connection.execute(
                    """
                    INSERT INTO nodes (
                        node_number,
                        first_seen,
                        last_seen
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(node_number)
                    DO UPDATE SET
                        last_seen = excluded.last_seen
                    """,
                    (
                        node_number,
                        now,
                        now,
                    ),
                )

                self.connection.execute(
                    """
                    INSERT INTO node_activity (
                        community_id,
                        node_number,
                        first_seen,
                        last_seen,
                        packets_received,
                        last_root,
                        last_channel
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(
                        community_id,
                        node_number
                    )
                    DO UPDATE SET
                        last_seen = excluded.last_seen,
                        packets_received = (
                            node_activity.packets_received
                            + 1
                        ),
                        last_root = excluded.last_root,
                        last_channel = excluded.last_channel
                    """,
                    (
                        community_id,
                        node_number,
                        now,
                        now,
                        mqtt_root,
                        channel_name,
                    ),
                )

            self.connection.execute(
                """
                INSERT INTO room_activity (
                    community_id,
                    mqtt_root,
                    channel_name,
                    first_seen,
                    last_seen,
                    packets_received,
                    packets_routed
                )
                VALUES (?, ?, ?, ?, ?, 1, 0)
                ON CONFLICT(
                    community_id,
                    mqtt_root,
                    channel_name
                )
                DO UPDATE SET
                    last_seen = excluded.last_seen,
                    packets_received = (
                        room_activity.packets_received
                        + 1
                    )
                """,
                (
                    community_id,
                    mqtt_root,
                    channel_name,
                    now,
                    now,
                ),
            )

            self.connection.execute(
                """
                INSERT INTO routing_statistics (
                    community_id,
                    packets_accepted,
                    packets_routed,
                    duplicates_blocked,
                    updated_at
                )
                VALUES (?, 1, 0, 0, ?)
                ON CONFLICT(community_id)
                DO UPDATE SET
                    packets_accepted = (
                        routing_statistics.packets_accepted
                        + 1
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    community_id,
                    now,
                ),
            )

            self.connection.commit()

    def record_routed_packet(
        self,
        community_id: int,
        mqtt_root: str,
        channel_name: str,
    ) -> None:
        now = int(time.time())

        mqtt_root = normalize_root(
            mqtt_root
        )

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO room_activity (
                    community_id,
                    mqtt_root,
                    channel_name,
                    first_seen,
                    last_seen,
                    packets_received,
                    packets_routed
                )
                VALUES (?, ?, ?, ?, ?, 0, 1)
                ON CONFLICT(
                    community_id,
                    mqtt_root,
                    channel_name
                )
                DO UPDATE SET
                    last_seen = excluded.last_seen,
                    packets_routed = (
                        room_activity.packets_routed
                        + 1
                    )
                """,
                (
                    community_id,
                    mqtt_root,
                    channel_name,
                    now,
                    now,
                ),
            )

            self.connection.execute(
                """
                INSERT INTO routing_statistics (
                    community_id,
                    packets_accepted,
                    packets_routed,
                    duplicates_blocked,
                    updated_at
                )
                VALUES (?, 0, 1, 0, ?)
                ON CONFLICT(community_id)
                DO UPDATE SET
                    packets_routed = (
                        routing_statistics.packets_routed
                        + 1
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    community_id,
                    now,
                ),
            )

            self.connection.commit()

    def record_duplicate_packet(
        self,
        community_id: int,
    ) -> None:
        now = int(time.time())

        with self.lock:
            self.connection.execute(
                """
                INSERT INTO routing_statistics (
                    community_id,
                    packets_accepted,
                    packets_routed,
                    duplicates_blocked,
                    updated_at
                )
                VALUES (?, 0, 0, 1, ?)
                ON CONFLICT(community_id)
                DO UPDATE SET
                    duplicates_blocked = (
                        routing_statistics.duplicates_blocked
                        + 1
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    community_id,
                    now,
                ),
            )

            self.connection.commit()

    def get_activity_summary(
        self,
        community_id: int,
        active_window_seconds: int,
    ) -> dict[str, int]:
        cutoff = (
            int(time.time())
            - active_window_seconds
        )

        with self.lock:
            active_nodes_row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM node_activity
                WHERE community_id = ?
                  AND last_seen >= ?
                """,
                (
                    community_id,
                    cutoff,
                ),
            ).fetchone()

            known_nodes_row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM node_activity
                WHERE community_id = ?
                """,
                (community_id,),
            ).fetchone()

            active_rooms_row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM room_activity
                WHERE community_id = ?
                  AND last_seen >= ?
                """,
                (
                    community_id,
                    cutoff,
                ),
            ).fetchone()

            known_rooms_row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM room_activity
                WHERE community_id = ?
                """,
                (community_id,),
            ).fetchone()

            statistics_row = self.connection.execute(
                """
                SELECT
                    packets_accepted,
                    packets_routed,
                    duplicates_blocked
                FROM routing_statistics
                WHERE community_id = ?
                """,
                (community_id,),
            ).fetchone()

        return {
            "active_hosts": int(
                active_nodes_row["count"]
                if active_nodes_row is not None
                else 0
            ),
            "known_hosts": int(
                known_nodes_row["count"]
                if known_nodes_row is not None
                else 0
            ),
            "active_rooms": int(
                active_rooms_row["count"]
                if active_rooms_row is not None
                else 0
            ),
            "known_rooms": int(
                known_rooms_row["count"]
                if known_rooms_row is not None
                else 0
            ),
            "packets_accepted": int(
                statistics_row["packets_accepted"]
                if statistics_row is not None
                else 0
            ),
            "packets_routed": int(
                statistics_row["packets_routed"]
                if statistics_row is not None
                else 0
            ),
            "duplicates_blocked": int(
                statistics_row["duplicates_blocked"]
                if statistics_row is not None
                else 0
            ),
            "active_window_seconds": (
                active_window_seconds
            ),
        }

    def get_active_nodes(
        self,
        community_id: int,
        active_window_seconds: int,
    ) -> list[dict[str, object]]:
        cutoff = (
            int(time.time())
            - active_window_seconds
        )

        with self.lock:
            rows = self.connection.execute(
                """
                SELECT
                    node_number,
                    first_seen,
                    last_seen,
                    packets_received,
                    last_root,
                    last_channel
                FROM node_activity
                WHERE community_id = ?
                  AND last_seen >= ?
                ORDER BY last_seen DESC
                """,
                (
                    community_id,
                    cutoff,
                ),
            ).fetchall()

        return [
            {
                "node_number": int(
                    row["node_number"]
                ),
                "node_id": (
                    f"!{int(row['node_number']):08x}"
                ),
                "first_seen": int(
                    row["first_seen"]
                ),
                "last_seen": int(
                    row["last_seen"]
                ),
                "packets_received": int(
                    row["packets_received"]
                ),
                "last_root": row["last_root"],
                "last_channel": row["last_channel"],
            }
            for row in rows
        ]

    def get_active_rooms(
        self,
        community_id: int,
        active_window_seconds: int,
    ) -> list[dict[str, object]]:
        cutoff = (
            int(time.time())
            - active_window_seconds
        )

        with self.lock:
            rows = self.connection.execute(
                """
                SELECT
                    mqtt_root,
                    channel_name,
                    first_seen,
                    last_seen,
                    packets_received,
                    packets_routed
                FROM room_activity
                WHERE community_id = ?
                  AND last_seen >= ?
                ORDER BY last_seen DESC
                """,
                (
                    community_id,
                    cutoff,
                ),
            ).fetchall()

        return [
            {
                "mqtt_root": str(
                    row["mqtt_root"]
                ),
                "channel_name": str(
                    row["channel_name"]
                ),
                "room": (
                    f"{row['mqtt_root']} "
                    f"/ {row['channel_name']}"
                ),
                "first_seen": int(
                    row["first_seen"]
                ),
                "last_seen": int(
                    row["last_seen"]
                ),
                "packets_received": int(
                    row["packets_received"]
                ),
                "packets_routed": int(
                    row["packets_routed"]
                ),
            }
            for row in rows
        ]

    def get_schema_version(
        self,
    ) -> int:
        with self.lock:
            row = self.connection.execute(
                """
                SELECT MAX(version) AS version
                FROM schema_migrations
                """
            ).fetchone()

        if (
            row is None
            or row["version"] is None
        ):
            return 0

        return int(
            row["version"]
        )

    def close(self) -> None:
        with self.lock:
            self.connection.close()
