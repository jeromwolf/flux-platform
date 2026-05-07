"""Web crawler node — HTTP GET + HTML parsing."""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register
class CrawlerNode(BaseNode):
    name = "crawler"
    display_name = "웹 크롤러"
    description = "웹 페이지 크롤링 + HTML 파싱"
    category = "network"

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Crawl a web page and extract content.

        Params:
            url: Target URL (required, or from input_data)
            extract: What to extract — "text", "html", "links", "all" (default: "text")
            timeout: Request timeout (default: 30)
        """
        url = params.get("url", "")

        # If no URL, try from input data
        if not url and input_data:
            url = input_data[0].get("url", input_data[0].get("text", ""))

        if not url:
            raise ValueError(
                "Crawler node requires 'url' parameter or input data with 'url'"
            )

        extract_mode = params.get("extract", "text")
        timeout = float(params.get("timeout", 30))

        # SSRF protection
        from core.workflow.nodes.url_validator import validate_url, SSRFError
        try:
            validate_url(url)
        except SSRFError as exc:
            raise ValueError(f"SSRF blocked: {exc}") from exc

        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=False
        ) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "IMSP-Crawler/1.0 (Maritime Research Platform)"
                },
            )
            response.raise_for_status()

        html = response.text
        result: dict[str, Any] = {
            "url": str(response.url),
            "status_code": response.status_code,
        }

        if extract_mode == "html":
            result["html"] = html
        elif extract_mode == "links":
            # Simple regex link extraction (avoid BeautifulSoup dependency)
            links = re.findall(r'href=["\']([^"\']+)["\']', html)
            result["links"] = links
        elif extract_mode == "all":
            # Strip HTML tags for text
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            links = re.findall(r'href=["\']([^"\']+)["\']', html)
            result["text"] = text[:50000]  # Limit to 50KB text
            result["html"] = html[:200000]  # Limit to 200KB HTML
            result["links"] = links
        else:
            # text mode — strip HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            result["text"] = text[:50000]

        return [result]

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "크롤링 대상 URL"},
                "extract": {
                    "type": "string",
                    "enum": ["text", "html", "links", "all"],
                    "default": "text",
                    "description": "추출 모드",
                },
                "timeout": {
                    "type": "number",
                    "default": 30,
                    "description": "타임아웃 (초)",
                },
            },
        }
