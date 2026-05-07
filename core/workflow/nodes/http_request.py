"""HTTP request node — REST API calls."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register
class HttpRequestNode(BaseNode):
    name = "api"
    display_name = "API 호출"
    description = "REST API 호출 (GET/POST/PUT/DELETE)"
    category = "network"

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Make HTTP request.

        Params:
            url: Target URL (required)
            method: HTTP method (default: GET)
            headers: Dict of request headers
            body: Request body (for POST/PUT)
            timeout: Request timeout in seconds (default: 30)
        """
        url = params.get("url", "")
        if not url:
            raise ValueError("HTTP Request node requires 'url' parameter")

        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        body = params.get("body")
        timeout = float(params.get("timeout", 30))

        # Template substitution: replace {{field}} with values from input_data
        if input_data:
            first = input_data[0]
            for key, val in first.items():
                url = url.replace(f"{{{{{key}}}}}", str(val))
                if isinstance(body, str):
                    body = body.replace(f"{{{{{key}}}}}", str(val))

        # SSRF protection
        from core.workflow.nodes.url_validator import validate_url, SSRFError
        try:
            validate_url(url)
        except SSRFError as exc:
            raise ValueError(f"SSRF blocked: {exc}") from exc

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                content=body if isinstance(body, str) else None,
            )

        try:
            response_data = response.json()
        except Exception:
            response_data = response.text

        result = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_data,
        }

        # If response is a list, return each item
        if isinstance(response_data, list):
            return [
                {"item": item, "status_code": response.status_code}
                for item in response_data
            ]

        return [result]

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "description": "요청 URL"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                    "description": "HTTP 메서드",
                },
                "headers": {
                    "type": "object",
                    "default": {},
                    "description": "요청 헤더",
                },
                "body": {
                    "description": "요청 바디 (POST/PUT용)",
                },
                "timeout": {
                    "type": "number",
                    "default": 30,
                    "description": "타임아웃 (초)",
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if not params.get("url"):
            errors.append("'url' is required")
        return errors
