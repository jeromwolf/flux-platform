"""Built-in workflow nodes — auto-registered on import."""
# Import all node modules to trigger @NodeRegistry.register decorators.
# Nodes are imported conditionally to allow partial loading during development.

import importlib
import logging

logger = logging.getLogger(__name__)

_BUILTIN_NODES = [
    "core.workflow.nodes.data_input",
    "core.workflow.nodes.http_request",
    "core.workflow.nodes.crawler",
    "core.workflow.nodes.transform",
    "core.workflow.nodes.llm",
    "core.workflow.nodes.neo4j_output",
]

for _mod_path in _BUILTIN_NODES:
    try:
        importlib.import_module(_mod_path)
    except ImportError as e:
        logger.debug(f"Optional node module not available: {_mod_path} ({e})")
