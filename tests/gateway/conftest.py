"""Fixtures and configuration for gateway tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so that the top-level `gateway`
# package is importable when pytest collects tests/gateway/ as a sub-package.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
