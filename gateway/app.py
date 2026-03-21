"""Gateway application factory."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway.config import GatewayConfig
from gateway.middleware.ws_auth import WSAuthConfig, WSAuthenticator
from gateway.routes.proxy import APIProxy, ProxyRoute


@dataclass
class GatewayApp:
    """Gateway application descriptor.

    Holds configuration and all assembled components without requiring
    FastAPI or any ASGI framework at import time. An actual ASGI adapter
    can wrap this descriptor at startup.

    Attributes:
        config: Resolved gateway configuration.
        proxy: Configured API proxy instance.
        ws_auth: WebSocket authenticator instance.
        routes: Ordered list of proxy route definitions.
    """

    config: GatewayConfig
    proxy: APIProxy
    ws_auth: WSAuthenticator
    routes: list[ProxyRoute]

    @classmethod
    def create(cls, config: GatewayConfig | None = None) -> GatewayApp:
        """Assemble and return a fully configured :class:`GatewayApp`.

        If *config* is ``None``, :meth:`GatewayConfig.from_env` is called
        to build the configuration from environment variables.

        The factory validates the resolved configuration and raises
        :class:`ValueError` if it contains any errors.

        Args:
            config: Optional pre-built configuration. Defaults to env-derived
                config when ``None``.

        Returns:
            A configured :class:`GatewayApp` descriptor ready for mounting
            inside an ASGI framework.

        Raises:
            ValueError: If the resolved configuration fails validation.
        """
        resolved = config if config is not None else GatewayConfig.from_env()

        errors = resolved.validate()
        if errors:
            joined = "; ".join(errors)
            raise ValueError(f"Invalid GatewayConfig: {joined}")

        proxy = APIProxy(base_url=resolved.api_base_url)
        ws_auth_config = WSAuthConfig.from_env()
        ws_auth = WSAuthenticator(config=ws_auth_config)
        routes = proxy.get_routes()

        return cls(
            config=resolved,
            proxy=proxy,
            ws_auth=ws_auth,
            routes=routes,
        )

    def describe(self) -> dict[str, Any]:
        """Return a human-readable descriptor of the gateway app.

        Useful for health-check endpoints and startup logging.

        Returns:
            Dictionary summarising the app's configuration and routes.
        """
        return {
            "host": self.config.host,
            "port": self.config.port,
            "api_base_url": self.config.api_base_url,
            "ws_max_connections": self.config.ws_max_connections,
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
            "debug": self.config.debug,
            "routes": [
                {
                    "path": r.path,
                    "methods": list(r.methods),
                    "require_auth": r.require_auth,
                    "timeout": r.timeout,
                }
                for r in self.routes
            ],
        }


def create_gateway_app(config: GatewayConfig | None = None) -> GatewayApp:
    """Create the API Gateway application.

    Convenience wrapper around :meth:`GatewayApp.create`. Returns a
    configured :class:`GatewayApp` descriptor (not an actual ASGI app)
    so that the module remains importable without FastAPI installed.

    In Y2+, this factory will also wire middleware (CORS, rate limiting,
    Keycloak token validation) and return a proper FastAPI/Starlette app.

    Args:
        config: Optional pre-built :class:`GatewayConfig`. When ``None``,
            configuration is loaded from ``GATEWAY_*`` environment variables.

    Returns:
        A fully assembled :class:`GatewayApp` descriptor.

    Raises:
        ValueError: If the resolved configuration fails validation.
    """
    return GatewayApp.create(config=config)
