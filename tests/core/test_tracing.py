"""Distributed tracing middleware unit tests.

TC-TR01 ~ TC-TR12: TraceContext and TracingMiddleware verification.
All tests run without network — pure Python only.
"""

from __future__ import annotations

import pytest

from kg.api.middleware.tracing import TraceContext, TracingMiddleware, _should_sample


# =============================================================================
# TC-TR01: TraceContext creation
# =============================================================================


@pytest.mark.unit
class TestTraceContext:
    """TraceContext dataclass tests."""

    def test_new_root_generates_valid_ids(self) -> None:
        """TC-TR01-a: new_root() generates 32-char trace_id and 16-char span_id."""
        ctx = TraceContext.new_root()
        assert len(ctx.trace_id) == 32
        assert len(ctx.span_id) == 16
        assert ctx.parent_span_id == ""
        assert ctx.sampled is True

    def test_new_root_unique(self) -> None:
        """TC-TR01-b: Each new_root() call generates unique IDs."""
        ctx1 = TraceContext.new_root()
        ctx2 = TraceContext.new_root()
        assert ctx1.trace_id != ctx2.trace_id
        assert ctx1.span_id != ctx2.span_id

    def test_new_root_sampled_false(self) -> None:
        """TC-TR01-c: new_root(sampled=False) sets sampled=False."""
        ctx = TraceContext.new_root(sampled=False)
        assert ctx.sampled is False

    def test_frozen_dataclass(self) -> None:
        """TC-TR01-d: TraceContext is frozen."""
        ctx = TraceContext.new_root()
        with pytest.raises(AttributeError):
            ctx.trace_id = "new_value"  # type: ignore[misc]


# =============================================================================
# TC-TR02: Traceparent format
# =============================================================================


@pytest.mark.unit
class TestTraceparent:
    """W3C Traceparent header formatting and parsing."""

    def test_to_traceparent_format(self) -> None:
        """TC-TR02-a: to_traceparent() returns correct W3C format."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id="",
            sampled=True,
        )
        assert ctx.to_traceparent() == f"00-{'a' * 32}-{'b' * 16}-01"

    def test_to_traceparent_unsampled(self) -> None:
        """TC-TR02-b: Unsampled flag produces '00'."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id="",
            sampled=False,
        )
        assert ctx.to_traceparent().endswith("-00")

    def test_from_traceparent_valid(self) -> None:
        """TC-TR02-c: Parse valid traceparent header."""
        header = f"00-{'a' * 32}-{'b' * 16}-01"
        ctx = TraceContext.from_traceparent(header)
        assert ctx is not None
        assert ctx.trace_id == "a" * 32
        assert ctx.parent_span_id == "b" * 16
        assert ctx.sampled is True
        # New span_id should be generated (not same as parent)
        assert ctx.span_id != "b" * 16
        assert len(ctx.span_id) == 16

    def test_from_traceparent_malformed_parts(self) -> None:
        """TC-TR02-d: Malformed header returns None."""
        assert TraceContext.from_traceparent("invalid") is None
        assert TraceContext.from_traceparent("00-abc-def-01") is None

    def test_from_traceparent_invalid_hex(self) -> None:
        """TC-TR02-e: Non-hex characters return None."""
        header = f"00-{'g' * 32}-{'b' * 16}-01"
        assert TraceContext.from_traceparent(header) is None

    def test_from_traceparent_wrong_length(self) -> None:
        """TC-TR02-f: Wrong length trace_id returns None."""
        header = f"00-{'a' * 31}x-{'b' * 16}-01"
        # 'x' is valid hex but total length is still 32, so let's test actual wrong length
        header2 = f"00-{'a' * 30}-{'b' * 16}-01"
        assert TraceContext.from_traceparent(header2) is None


# =============================================================================
# TC-TR03: Sampling
# =============================================================================


@pytest.mark.unit
class TestSampling:
    """Trace sampling logic."""

    def test_default_sample_rate_always_samples(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-TR03-a: Default TRACE_SAMPLE_RATE=1.0 always samples."""
        monkeypatch.delenv("TRACE_SAMPLE_RATE", raising=False)
        # Should always return True with default rate
        results = [_should_sample() for _ in range(20)]
        assert all(results)

    def test_zero_sample_rate_never_samples(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-TR03-b: TRACE_SAMPLE_RATE=0.0 never samples."""
        monkeypatch.setenv("TRACE_SAMPLE_RATE", "0.0")
        results = [_should_sample() for _ in range(20)]
        assert not any(results)

    def test_invalid_sample_rate_defaults_to_full(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-TR03-c: Invalid TRACE_SAMPLE_RATE defaults to 1.0."""
        monkeypatch.setenv("TRACE_SAMPLE_RATE", "not_a_number")
        assert _should_sample() is True


# =============================================================================
# TC-TR04: Roundtrip
# =============================================================================


@pytest.mark.unit
class TestTraceparentRoundtrip:
    """Verify traceparent roundtrip consistency."""

    def test_roundtrip_preserves_trace_id(self) -> None:
        """TC-TR04-a: to_traceparent → from_traceparent preserves trace_id."""
        original = TraceContext.new_root()
        header = original.to_traceparent()
        parsed = TraceContext.from_traceparent(header)
        assert parsed is not None
        assert parsed.trace_id == original.trace_id
        # parent_span_id of parsed = span_id of original
        assert parsed.parent_span_id == original.span_id
