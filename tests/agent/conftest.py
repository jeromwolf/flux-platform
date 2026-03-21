"""Shared fixtures for agent tests.

Adds the project root to sys.path so that `agent.*` modules are importable
regardless of the pytest pythonpath configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Project root is three levels up from this file:
#   tests/agent/conftest.py -> tests/agent -> tests -> <project root>
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
