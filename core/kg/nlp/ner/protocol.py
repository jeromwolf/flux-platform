"""Protocol definition for Named Entity Recognition taggers.

Any class that implements the methods and properties below satisfies
the NERTagger protocol without needing to explicitly inherit from it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kg.nlp.ner.models import NERTag, NERTagType


@runtime_checkable
class NERTagger(Protocol):
    """Protocol for named entity taggers.

    Implementors perform entity extraction over raw text and declare
    which entity types they support.  The protocol is runtime-checkable,
    so ``isinstance(obj, NERTagger)`` returns True for any conforming object.
    """

    def tag(self, text: str) -> list[NERTag]:
        """Extract named entities from *text*.

        Args:
            text: Raw input string to analyse.

        Returns:
            List of NERTag instances found in the text, sorted by start
            offset ascending.  May be empty.
        """
        ...

    @property
    def name(self) -> str:
        """A short identifier for this tagger (e.g. "dictionary", "regex").

        Used to populate NERTag.source during tagging.
        """
        ...

    @property
    def supported_types(self) -> frozenset[NERTagType]:
        """The set of NERTagType values this tagger is capable of detecting.

        Callers may use this to filter or compose taggers by domain.
        """
        ...
