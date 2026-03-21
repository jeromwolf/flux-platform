"""Shared Cypher file parser utility.

Parses .cypher files delimited by ``;``, strips ``//`` comments and blank lines.
Used by the schema initializer, RBAC loader, and migration framework.
"""
from __future__ import annotations

from pathlib import Path


def parse_cypher_file(filepath: Path) -> list[str]:
    """Parse a .cypher file and return individual statements.

    Lines starting with ``//`` are treated as comments and ignored.
    Statements are delimited by ``;``.

    Args:
        filepath: Path to the .cypher file.

    Returns:
        List of non-empty Cypher statement strings.
    """
    text = filepath.read_text(encoding="utf-8")
    statements: list[str] = []
    for raw in text.split(";"):
        lines = [
            line
            for line in raw.strip().splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        stmt = " ".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements
