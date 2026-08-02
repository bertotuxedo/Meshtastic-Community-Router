from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from importlib import resources


LOGGER = logging.getLogger("mcr.migrations")

MIGRATION_FILENAME_PATTERN = re.compile(
    r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$"
)


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    filename: str
    sql: str
    checksum: str


class MigrationError(RuntimeError):
    pass


class MigrationRunner:
    def __init__(
        self,
        connection: sqlite3.Connection,
        package: str = "mcr.migrations",
    ) -> None:
        self.connection = connection
        self.package = package

    def initialize_migration_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                filename TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at INTEGER NOT NULL
            )
            """
        )
        self.connection.commit()

    def discover_migrations(
        self,
    ) -> list[Migration]:
        migration_package = resources.files(
            self.package
        )

        discovered: list[Migration] = []

        for resource in migration_package.iterdir():
            if not resource.is_file():
                continue

            match = MIGRATION_FILENAME_PATTERN.match(
                resource.name
            )

            if match is None:
                continue

            sql = resource.read_text(
                encoding="utf-8"
            )

            checksum = hashlib.sha256(
                sql.encode("utf-8")
            ).hexdigest()

            discovered.append(
                Migration(
                    version=int(
                        match.group("version")
                    ),
                    name=match.group("name"),
                    filename=resource.name,
                    sql=sql,
                    checksum=checksum,
                )
            )

        discovered.sort(
            key=lambda migration: migration.version
        )

        versions = [
            migration.version
            for migration in discovered
        ]

        if len(versions) != len(set(versions)):
            raise MigrationError(
                "Duplicate migration version detected"
            )

        return discovered

    def get_applied_migrations(
        self,
    ) -> dict[int, sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                version,
                name,
                filename,
                checksum,
                applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        return {
            int(row["version"]): row
            for row in rows
        }

    def verify_applied_migrations(
        self,
        available: list[Migration],
        applied: dict[int, sqlite3.Row],
    ) -> None:
        available_by_version = {
            migration.version: migration
            for migration in available
        }

        for version, row in applied.items():
            migration = available_by_version.get(
                version
            )

            if migration is None:
                raise MigrationError(
                    "Applied migration is missing from "
                    f"the application: {version:04d}"
                )

            stored_checksum = str(
                row["checksum"]
            )

            if stored_checksum != migration.checksum:
                raise MigrationError(
                    "Applied migration was modified: "
                    f"{migration.filename}"
                )

    def apply_migration(
        self,
        migration: Migration,
    ) -> None:
        LOGGER.info(
            "Applying migration %04d_%s",
            migration.version,
            migration.name,
        )

        try:
            self.connection.execute(
                "BEGIN IMMEDIATE"
            )

            self.connection.executescript(
                migration.sql
            )

            self.connection.execute(
                """
                INSERT INTO schema_migrations (
                    version,
                    name,
                    filename,
                    checksum,
                    applied_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    migration.filename,
                    migration.checksum,
                    int(time.time()),
                ),
            )

            self.connection.commit()
        except Exception as exc:
            self.connection.rollback()

            raise MigrationError(
                "Migration failed: "
                f"{migration.filename}: {exc}"
            ) from exc

        LOGGER.info(
            "Migration applied: %s",
            migration.filename,
        )

    def run(self) -> list[Migration]:
        self.initialize_migration_table()

        available = self.discover_migrations()
        applied = self.get_applied_migrations()

        self.verify_applied_migrations(
            available=available,
            applied=applied,
        )

        pending = [
            migration
            for migration in available
            if migration.version not in applied
        ]

        if not pending:
            LOGGER.info(
                "Database schema is current; "
                "%s migration(s) applied",
                len(applied),
            )
            return []

        for migration in pending:
            self.apply_migration(
                migration
            )

        LOGGER.info(
            "Database migrations complete; "
            "%s migration(s) applied",
            len(pending),
        )

        return pending
