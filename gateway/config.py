"""API Gateway configuration."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GatewayConfig:
    """API Gateway configuration.

    Attributes:
        host: Bind address for the gateway server.
        port: TCP port to listen on.
        cors_origins: Allowed CORS origins.
        api_base_url: Base URL of the Core KG API backend.
        ws_ping_interval: Seconds between WebSocket ping frames.
        ws_max_connections: Maximum simultaneous WebSocket connections.
        rate_limit_per_minute: Maximum requests per client per minute.
        debug: Enable debug mode (verbose logging, reload, etc.).
    """

    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: tuple[str, ...] = ("http://localhost:5180",)
    api_base_url: str = "http://localhost:8000"
    ws_ping_interval: float = 30.0
    ws_max_connections: int = 1000
    rate_limit_per_minute: int = 300
    debug: bool = False

    @classmethod
    def from_env(cls) -> GatewayConfig:
        """Load configuration from GATEWAY_* environment variables.

        Environment variables:
            GATEWAY_HOST: Bind address (default: 0.0.0.0)
            GATEWAY_PORT: TCP port (default: 8080)
            GATEWAY_CORS_ORIGINS: Comma-separated list of allowed origins
            GATEWAY_API_BASE_URL: Core KG API base URL
            GATEWAY_WS_PING_INTERVAL: WebSocket ping interval in seconds
            GATEWAY_WS_MAX_CONNECTIONS: Max concurrent WebSocket connections
            GATEWAY_RATE_LIMIT_PER_MINUTE: Max requests per client per minute
            GATEWAY_DEBUG: Enable debug mode (1/true/yes)

        Returns:
            A :class:`GatewayConfig` instance populated from environment.
        """
        raw_origins = os.getenv("GATEWAY_CORS_ORIGINS", "http://localhost:5180")
        cors_origins = tuple(
            o.strip() for o in raw_origins.split(",") if o.strip()
        )

        debug_raw = os.getenv("GATEWAY_DEBUG", "false").lower()
        debug = debug_raw in ("1", "true", "yes")

        return cls(
            host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
            port=int(os.getenv("GATEWAY_PORT", "8080")),
            cors_origins=cors_origins,
            api_base_url=os.getenv("GATEWAY_API_BASE_URL", "http://localhost:8000"),
            ws_ping_interval=float(os.getenv("GATEWAY_WS_PING_INTERVAL", "30.0")),
            ws_max_connections=int(os.getenv("GATEWAY_WS_MAX_CONNECTIONS", "1000")),
            rate_limit_per_minute=int(os.getenv("GATEWAY_RATE_LIMIT_PER_MINUTE", "300")),
            debug=debug,
        )

    def validate(self) -> list[str]:
        """Validate configuration values.

        Returns:
            List of validation error messages. Empty list means config is valid.
        """
        errors: list[str] = []

        # Port range check
        if not (1 <= self.port <= 65535):
            errors.append(f"port must be between 1 and 65535, got {self.port}")

        # URL format check (simple scheme+host validation)
        url_pattern = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
        if not url_pattern.match(self.api_base_url):
            errors.append(
                f"api_base_url must be a valid HTTP/HTTPS URL, got '{self.api_base_url}'"
            )

        # Ping interval
        if self.ws_ping_interval <= 0:
            errors.append(
                f"ws_ping_interval must be positive, got {self.ws_ping_interval}"
            )

        # Max connections
        if self.ws_max_connections < 1:
            errors.append(
                f"ws_max_connections must be >= 1, got {self.ws_max_connections}"
            )

        # Rate limit
        if self.rate_limit_per_minute < 1:
            errors.append(
                f"rate_limit_per_minute must be >= 1, got {self.rate_limit_per_minute}"
            )

        return errors
