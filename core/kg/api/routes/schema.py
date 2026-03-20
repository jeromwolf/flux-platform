"""Schema introspection endpoint."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from kg.api.deps import get_async_neo4j_session
from kg.api.entity_groups import (
    ENTITY_GROUPS,
    GROUP_COLORS,
    get_color_for_label,
    get_group_for_label,
)
from kg.api.models import SchemaResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["schema"])


@router.get("/api/schema", response_model=SchemaResponse)
async def schema(
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> SchemaResponse:
    """Return available labels, relationship types, and entity group metadata."""
    # Get node labels
    labels_result = await session.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
    labels_info: list[dict[str, Any]] = []
    labels_records = [record async for record in labels_result]
    for record in labels_records:
        lbl = record["label"]
        labels_info.append(
            {
                "label": lbl,
                "group": get_group_for_label(lbl),
                "color": get_color_for_label(lbl),
            }
        )

    # Get relationship types
    rel_result = await session.run(
        "CALL db.relationshipTypes() YIELD relationshipType "
        "RETURN relationshipType ORDER BY relationshipType"
    )
    rel_records = [record async for record in rel_result]
    rel_types = [record["relationshipType"] for record in rel_records]

    # Get node counts per label
    label_counts: dict[str, int] = {}
    for lbl_info in labels_info:
        lbl = lbl_info["label"]
        if not lbl.isidentifier():
            label_counts[lbl] = 0
            continue
        try:
            cnt_result = await session.run(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
            cnt_record = await cnt_result.single()
            label_counts[lbl] = cnt_record["cnt"] if cnt_record else 0
        except Exception:
            label_counts[lbl] = 0

    # Add counts to labels
    for lbl_info in labels_info:
        lbl_info["count"] = label_counts.get(lbl_info["label"], 0)

    entity_groups_dict = {
        group: {
            "color": color,
            "labels": ENTITY_GROUPS.get(group, []),
        }
        for group, color in GROUP_COLORS.items()
    }

    return SchemaResponse(
        labels=labels_info,  # type: ignore[arg-type]
        relationshipTypes=rel_types,
        entityGroups=entity_groups_dict,
        totalLabels=len(labels_info),
        totalRelationshipTypes=len(rel_types),
    )
