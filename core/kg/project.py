"""Multi-project KG namespace management.

Provides KGProjectContext for isolating knowledge graph data by project.
Each project gets a unique Neo4j label (e.g., KG_DevKG) applied to all nodes,
enabling logical partitioning within a single Neo4j Community Edition database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Valid: starts with letter, alphanumeric + underscore, 1-64 chars
_PROJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

DEFAULT_PROJECT = "default"
PROJECT_LABEL_PREFIX = "KG_"
PROJECT_HEADER = "X-KG-Project"


@dataclass(frozen=True)
class KGProjectContext:
    """Immutable project context extracted from request headers.

    Attributes:
        name: Validated project name (e.g., "DevKG", "default").
    """

    name: str

    @property
    def label(self) -> str:
        """Neo4j label string (e.g., "KG_DevKG")."""
        return f"{PROJECT_LABEL_PREFIX}{self.name}"

    @property
    def property_value(self) -> str:
        """Value for the _kg_project property stamp."""
        return self.name

    @classmethod
    def from_header(cls, header_value: str | None) -> KGProjectContext:
        """Create context from the X-KG-Project header value.

        Falls back to DEFAULT_PROJECT when header is absent or empty.
        Raises ValueError for invalid project names.
        """
        raw = (header_value or "").strip()
        if not raw:
            raw = DEFAULT_PROJECT
        if not _PROJECT_NAME_RE.match(raw):
            raise ValueError(
                f"Invalid project name '{raw}': "
                f"must match {_PROJECT_NAME_RE.pattern}"
            )
        return cls(name=raw)


def project_label(name: str) -> str:
    """Return the Neo4j label for a project name."""
    return f"{PROJECT_LABEL_PREFIX}{name}"
