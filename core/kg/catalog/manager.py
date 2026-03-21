"""In-memory registry for KG catalog entries.

CatalogManager maintains a dictionary of CatalogEntry objects keyed by their
``id`` field. Because CatalogEntry is frozen, mutations (quality updates,
schema history appends) produce replacement objects rather than in-place edits.
"""

from __future__ import annotations

import logging

from kg.catalog.models import CatalogEntry, QualityScore, SchemaChange
from kg.catalog.quality import calculate_quality_score

logger = logging.getLogger(__name__)


class CatalogManager:
    """In-memory registry for KG asset catalog entries.

    Entries are keyed by ``CatalogEntry.id``. Because CatalogEntry is
    frozen, any mutation creates a new entry object that replaces the
    previous one in the registry.

    Example::

        manager = CatalogManager()
        entry = CatalogEntry(id="node.Vessel", name="Vessel", entry_type="NODE_LABEL")
        manager.register(entry)
        result = manager.get("node.Vessel")
    """

    def __init__(self) -> None:
        self._registry: dict[str, CatalogEntry] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, entry: CatalogEntry) -> CatalogEntry:
        """Add or replace an entry in the registry.

        If an entry with the same ``id`` already exists it is silently
        overwritten. Use :meth:`get` beforehand if you need to check.

        Args:
            entry: The catalog entry to register.

        Returns:
            The registered entry (same object that was passed in).
        """
        self._registry[entry.id] = entry
        logger.debug("Registered catalog entry: id=%s type=%s", entry.id, entry.entry_type)
        return entry

    def get(self, entry_id: str) -> CatalogEntry | None:
        """Retrieve an entry by its identifier.

        Args:
            entry_id: The unique entry identifier.

        Returns:
            The matching CatalogEntry, or ``None`` if not found.
        """
        return self._registry.get(entry_id)

    def list_all(self) -> list[CatalogEntry]:
        """Return all registered entries sorted alphabetically by name.

        Returns:
            Sorted list of all CatalogEntry objects in the registry.
        """
        return sorted(self._registry.values(), key=lambda e: e.name.lower())

    def list_by_type(self, entry_type: str) -> list[CatalogEntry]:
        """Return all entries whose ``entry_type`` matches the given value.

        Args:
            entry_type: One of "NODE_LABEL", "RELATIONSHIP_TYPE", "INDEX",
                "CONSTRAINT".

        Returns:
            List of matching CatalogEntry objects sorted by name.
        """
        return sorted(
            (e for e in self._registry.values() if e.entry_type == entry_type),
            key=lambda e: e.name.lower(),
        )

    def search(self, query: str) -> list[CatalogEntry]:
        """Case-insensitive substring search across ``name`` and ``description``.

        Args:
            query: Search string (matched against name and description).

        Returns:
            List of matching CatalogEntry objects sorted by name.
        """
        lower_query = query.lower()
        matches = [
            e
            for e in self._registry.values()
            if lower_query in e.name.lower() or lower_query in e.description.lower()
        ]
        return sorted(matches, key=lambda e: e.name.lower())

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from the registry.

        Args:
            entry_id: The unique identifier of the entry to remove.

        Returns:
            ``True`` if the entry existed and was removed, ``False`` otherwise.
        """
        if entry_id in self._registry:
            del self._registry[entry_id]
            logger.debug("Removed catalog entry: id=%s", entry_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Mutation helpers (frozen-safe — produce replacement objects)
    # ------------------------------------------------------------------

    def update_quality(
        self,
        entry_id: str,
        scores: list[QualityScore],
    ) -> CatalogEntry | None:
        """Replace the quality_scores on a registered entry.

        Because CatalogEntry is frozen, a new object is constructed with the
        updated ``quality_scores`` tuple and stored under the same id.

        Args:
            entry_id: The identifier of the entry to update.
            scores: New list of QualityScore objects to store.

        Returns:
            The updated CatalogEntry, or ``None`` if ``entry_id`` is not found.
        """
        existing = self._registry.get(entry_id)
        if existing is None:
            logger.warning("update_quality: entry not found — id=%s", entry_id)
            return None

        updated = CatalogEntry(
            id=existing.id,
            name=existing.name,
            entry_type=existing.entry_type,
            description=existing.description,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            owner=existing.owner,
            tags=existing.tags,
            quality_scores=tuple(scores),
            schema_history=existing.schema_history,
            properties=existing.properties,
        )
        self._registry[entry_id] = updated
        logger.debug("Updated quality scores for entry: id=%s", entry_id)
        return updated

    def add_schema_change(
        self,
        entry_id: str,
        change: SchemaChange,
    ) -> CatalogEntry | None:
        """Append a SchemaChange to the entry's schema_history.

        Because CatalogEntry is frozen, a new object is created with the
        change appended to the existing ``schema_history`` tuple.

        Args:
            entry_id: The identifier of the entry to update.
            change: The SchemaChange to append.

        Returns:
            The updated CatalogEntry, or ``None`` if ``entry_id`` is not found.
        """
        existing = self._registry.get(entry_id)
        if existing is None:
            logger.warning("add_schema_change: entry not found — id=%s", entry_id)
            return None

        updated = CatalogEntry(
            id=existing.id,
            name=existing.name,
            entry_type=existing.entry_type,
            description=existing.description,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            owner=existing.owner,
            tags=existing.tags,
            quality_scores=existing.quality_scores,
            schema_history=existing.schema_history + (change,),
            properties=existing.properties,
        )
        self._registry[entry_id] = updated
        logger.debug(
            "Added schema change to entry: id=%s version=%s type=%s",
            entry_id,
            change.version,
            change.change_type,
        )
        return updated

    def refresh_quality(self, entry_id: str) -> CatalogEntry | None:
        """Recalculate and store quality scores for a registered entry.

        Calls :func:`~kg.catalog.quality.calculate_quality_score` and then
        delegates to :meth:`update_quality`.

        Args:
            entry_id: The identifier of the entry to refresh.

        Returns:
            The updated CatalogEntry with fresh quality scores, or ``None``
            if ``entry_id`` is not found.
        """
        existing = self._registry.get(entry_id)
        if existing is None:
            logger.warning("refresh_quality: entry not found — id=%s", entry_id)
            return None

        new_scores = calculate_quality_score(existing)
        return self.update_quality(entry_id, new_scores)
