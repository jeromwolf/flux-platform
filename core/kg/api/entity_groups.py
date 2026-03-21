"""Backward compatibility shim — use maritime.entity_groups instead."""
import warnings

warnings.warn(
    "Importing from 'kg.api.entity_groups' is deprecated. "
    "Use 'maritime.entity_groups' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from maritime.entity_groups import *  # noqa: F401,F403
    from maritime.entity_groups import _LABEL_TO_GROUP  # noqa: F401
except ImportError:
    # Fallback: maritime 패키지가 경로에 없을 경우 기본값 제공
    _LABEL_TO_GROUP: dict = {}  # type: ignore[no-redef]

    def get_color_for_label(label: str) -> str:  # type: ignore[misc]
        return "#999999"

    def get_group_for_label(label: str) -> str:  # type: ignore[misc]
        return "unknown"
