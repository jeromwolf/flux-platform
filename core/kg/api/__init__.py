"""Maritime KG REST API package.

Provides a FastAPI application for exploring the Maritime Knowledge Graph.
"""

from __future__ import annotations

from kg.api.app import create_app

__all__ = ["create_app"]
