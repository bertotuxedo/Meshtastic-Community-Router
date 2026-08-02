from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from importlib import resources
from typing import Any


LOGGER = logging.getLogger("mcr.api")

StatusProvider = Callable[
    [],
    dict[str, Any],
]


class StatusApi:
    def __init__(
        self,
        host: str,
        port: int,
        status_provider: StatusProvider,
    ) -> None:
        self.host = host
        self.port = port
        self.status_provider = status_provider

        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.started_at = time.time()

        self.dashboard_html = (
            resources.files("mcr.web")
            .joinpath("index.html")
            .read_bytes()
        )

    def build_handler(
        self,
    ) -> type[BaseHTTPRequestHandler]:
        api = self

        class RequestHandler(
            BaseHTTPRequestHandler
        ):
            server_version = (
                "MeshtasticCommunityRouterAPI/0.2"
            )

            def do_GET(self) -> None:
                try:
                    api.handle_get(self)
                except Exception:
                    LOGGER.exception(
                        "Unhandled API request error "
                        "path=%s",
                        self.path,
                    )

                    api.send_json(
                        handler=self,
                        status=(
                            HTTPStatus
                            .INTERNAL_SERVER_ERROR
                        ),
                        payload={
                            "error": (
                                "internal_server_error"
                            ),
                            "message": (
                                "An internal API error "
                                "occurred."
                            ),
                        },
                    )

            def log_message(
                self,
                format_string: str,
                *arguments: object,
            ) -> None:
                LOGGER.info(
                    "%s - %s",
                    self.address_string(),
                    format_string % arguments,
                )

        return RequestHandler

    def handle_get(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> None:
        path = handler.path.split(
            "?",
            maxsplit=1,
        )[0].rstrip("/")

        if not path:
            path = "/"

        if path == "/":
            self.send_content(
                handler=handler,
                status=HTTPStatus.OK,
                content_type=(
                    "text/html; charset=utf-8"
                ),
                content=self.dashboard_html,
            )
            return

        if path == "/health":
            self.send_json(
                handler=handler,
                status=HTTPStatus.OK,
                payload={
                    "status": "ok",
                    "uptime_seconds": int(
                        time.time()
                        - self.started_at
                    ),
                },
            )
            return

        status = self.status_provider()

        if path == "/api/status":
            self.send_json(
                handler=handler,
                status=HTTPStatus.OK,
                payload=status,
            )
            return

        if path == "/api/roots":
            self.send_json(
                handler=handler,
                status=HTTPStatus.OK,
                payload={
                    "roots": status.get(
                        "roots",
                        [],
                    ),
                    "root_count": status.get(
                        "root_count",
                        0,
                    ),
                },
            )
            return

        if path == "/api/plugins":
            self.send_json(
                handler=handler,
                status=HTTPStatus.OK,
                payload={
                    "plugins": status.get(
                        "plugins",
                        [],
                    ),
                },
            )
            return

        if path == "/api/scheduler":
            self.send_json(
                handler=handler,
                status=HTTPStatus.OK,
                payload=status.get(
                    "scheduler",
                    {},
                ),
            )
            return

        self.send_json(
            handler=handler,
            status=HTTPStatus.NOT_FOUND,
            payload={
                "error": "not_found",
                "message": (
                    f"No endpoint exists at {path}."
                ),
            },
        )

    @staticmethod
    def send_content(
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        content_type: str,
        content: bytes,
    ) -> None:
        handler.send_response(
            int(status)
        )

        handler.send_header(
            "Content-Type",
            content_type,
        )

        handler.send_header(
            "Content-Length",
            str(len(content)),
        )

        handler.send_header(
            "Cache-Control",
            "no-store",
        )

        handler.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        handler.send_header(
            "X-Frame-Options",
            "DENY",
        )

        handler.end_headers()
        handler.wfile.write(content)

    @classmethod
    def send_json(
        cls,
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        payload: object,
    ) -> None:
        encoded = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        ).encode("utf-8")

        cls.send_content(
            handler=handler,
            status=status,
            content_type=(
                "application/json; charset=utf-8"
            ),
            content=encoded,
        )

    def start(self) -> None:
        if (
            self.thread is not None
            and self.thread.is_alive()
        ):
            return

        handler_class = self.build_handler()

        self.server = ThreadingHTTPServer(
            (
                self.host,
                self.port,
            ),
            handler_class,
        )

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="mcr-status-api",
            daemon=True,
        )

        self.thread.start()

        LOGGER.info(
            "Dashboard and read-only API listening "
            "on http://%s:%s",
            self.host,
            self.port,
        )

    def stop(self) -> None:
        server = self.server

        if server is not None:
            server.shutdown()
            server.server_close()

        thread = self.thread

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):
            thread.join(
                timeout=5,
            )

        self.server = None
        self.thread = None

        LOGGER.info(
            "Dashboard and status API stopped"
        )
