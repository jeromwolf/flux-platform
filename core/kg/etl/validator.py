"""Validation rules for ETL record envelopes.

Provides:
- ValidationRule: abstract base for validation checks
- RequiredFieldsRule: ensure specified fields exist and are non-empty
- TypeCheckRule: verify field values match expected types
- OntologyLabelRule: verify labels against the maritime ontology
- RecordValidator: compose multiple rules and collect errors
"""

from __future__ import annotations

import abc

from kg.etl.models import RecordEnvelope


class ValidationRule(abc.ABC):
    """Abstract base for a single validation check on a RecordEnvelope."""

    @abc.abstractmethod
    def validate(self, record: RecordEnvelope) -> list[str]:
        """Validate *record* and return a list of error messages.

        An empty list means the record passes this rule.

        Args:
            record: The record envelope to validate.

        Returns:
            List of human-readable error strings (empty if valid).
        """
        ...


class RequiredFieldsRule(ValidationRule):
    """Check that specified fields exist in the record data and are non-empty.

    Args:
        fields: Field names that must be present and non-empty.
    """

    def __init__(self, fields: list[str]) -> None:
        self._fields = fields

    def validate(self, record: RecordEnvelope) -> list[str]:
        """Return errors for any missing or empty required fields."""
        errors: list[str] = []
        for field_name in self._fields:
            value = record.data.get(field_name)
            if value is None:
                errors.append(f"Missing required field: {field_name}")
            elif isinstance(value, str) and not value.strip():
                errors.append(f"Empty required field: {field_name}")
        return errors


class TypeCheckRule(ValidationRule):
    """Check that field values match expected Python types.

    Args:
        schema: Mapping of field name to expected Python type
            (e.g. ``{"name": str, "age": int}``).
    """

    def __init__(self, schema: dict[str, type]) -> None:
        self._schema = schema

    def validate(self, record: RecordEnvelope) -> list[str]:
        """Return errors for fields with wrong types."""
        errors: list[str] = []
        for field_name, expected_type in self._schema.items():
            value = record.data.get(field_name)
            if value is not None and not isinstance(value, expected_type):
                actual = type(value).__name__
                errors.append(
                    f"Field '{field_name}' expected {expected_type.__name__}, "
                    f"got {actual}"
                )
        return errors


class OntologyLabelRule(ValidationRule):
    """Verify that a label field matches a set of valid entity labels.

    Args:
        label_field: Name of the data field containing the Neo4j label.
            Defaults to ``"label"``.
        valid_labels: Set of accepted label strings. When ``None`` (default),
            the rule falls back to loading labels from the maritime ontology
            module for backward compatibility. Pass an explicit set (including
            an empty set) to make the rule domain-independent.
    """

    def __init__(
        self,
        label_field: str = "label",
        valid_labels: set[str] | None = None,
    ) -> None:
        self._label_field = label_field
        if valid_labels is None:
            # Lazy import: preserve existing behaviour without a module-level
            # hard dependency on maritime_ontology.
            from kg.ontology.maritime_ontology import ENTITY_LABELS  # noqa: PLC0415

            self._valid_labels: set[str] = set(ENTITY_LABELS.keys())
        else:
            self._valid_labels = valid_labels

    def validate(self, record: RecordEnvelope) -> list[str]:
        """Return an error if the label is not in the set of valid labels.

        When ``valid_labels`` was initialised as an empty set all labels are
        accepted (the check is effectively disabled).
        """
        label = record.data.get(self._label_field)
        if label is None:
            return [f"Missing label field: {self._label_field}"]
        if self._valid_labels and label not in self._valid_labels:
            return [f"Unknown ontology label: '{label}'"]
        return []


class RecordValidator:
    """Compose multiple validation rules and validate a RecordEnvelope.

    Args:
        rules: List of validation rules to apply.
    """

    def __init__(self, rules: list[ValidationRule]) -> None:
        self._rules = list(rules)

    def validate(self, record: RecordEnvelope) -> list[str]:
        """Run all rules against *record* and return aggregated errors.

        Args:
            record: The record envelope to validate.

        Returns:
            Combined list of error messages from all rules.
        """
        errors: list[str] = []
        for rule in self._rules:
            errors.extend(rule.validate(record))
        return errors

    def add_rule(self, rule: ValidationRule) -> None:
        """Append an additional validation rule.

        Args:
            rule: The rule to add.
        """
        self._rules.append(rule)
