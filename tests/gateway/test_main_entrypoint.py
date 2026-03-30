"""Unit tests for gateway.__main__ (CLI entry point)."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_main(argv: list[str], env_overrides: dict | None = None) -> MagicMock:
    """Run gateway.main() with *argv* and return the mock uvicorn.run call."""
    env_overrides = env_overrides or {}

    # Import fresh each time so argparse state is not shared
    import importlib
    import gateway.__main__ as gm
    importlib.reload(gm)

    with patch.object(sys, "argv", ["gateway"] + argv):
        with patch.dict(os.environ, env_overrides, clear=False):
            # Clean up any previously set env vars
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run") as mock_run:
                gm.main()
                return mock_run


# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_default_host():
    mock_run = _run_main([])
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "0.0.0.0"


@pytest.mark.unit
def test_main_default_port():
    mock_run = _run_main([])
    _, kwargs = mock_run.call_args
    assert kwargs["port"] == 8080


@pytest.mark.unit
def test_main_default_debug_false():
    mock_run = _run_main([])
    _, kwargs = mock_run.call_args
    assert kwargs["reload"] is False


@pytest.mark.unit
def test_main_default_log_level_info():
    mock_run = _run_main([])
    _, kwargs = mock_run.call_args
    assert kwargs["log_level"] == "info"


@pytest.mark.unit
def test_main_default_app_string():
    mock_run = _run_main([])
    args, _ = mock_run.call_args
    assert args[0] == "gateway.server:app"


# ---------------------------------------------------------------------------
# Custom --host
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_custom_host():
    mock_run = _run_main(["--host", "127.0.0.1"])
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "127.0.0.1"


@pytest.mark.unit
def test_main_custom_host_sets_env_var():
    with patch.object(sys, "argv", ["gateway", "--host", "10.0.0.1"]):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert os.environ.get("GATEWAY_HOST") == "10.0.0.1"


# ---------------------------------------------------------------------------
# Custom --port
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_custom_port():
    mock_run = _run_main(["--port", "9090"])
    _, kwargs = mock_run.call_args
    assert kwargs["port"] == 9090


@pytest.mark.unit
def test_main_custom_port_sets_env_var():
    with patch.object(sys, "argv", ["gateway", "--port", "7749"]):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert os.environ.get("GATEWAY_PORT") == "7749"


# ---------------------------------------------------------------------------
# --debug flag
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_debug_enables_reload():
    mock_run = _run_main(["--debug"])
    _, kwargs = mock_run.call_args
    assert kwargs["reload"] is True


@pytest.mark.unit
def test_main_debug_sets_log_level_debug():
    mock_run = _run_main(["--debug"])
    _, kwargs = mock_run.call_args
    assert kwargs["log_level"] == "debug"


@pytest.mark.unit
def test_main_debug_sets_env_var():
    with patch.object(sys, "argv", ["gateway", "--debug"]):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert os.environ.get("GATEWAY_DEBUG") == "true"


@pytest.mark.unit
def test_main_no_debug_does_not_set_debug_env_var():
    with patch.object(sys, "argv", ["gateway"]):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert "GATEWAY_DEBUG" not in os.environ


# ---------------------------------------------------------------------------
# Combined args
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_combined_host_port_debug():
    mock_run = _run_main(["--host", "192.168.1.1", "--port", "8000", "--debug"])
    args, kwargs = mock_run.call_args
    assert args[0] == "gateway.server:app"
    assert kwargs["host"] == "192.168.1.1"
    assert kwargs["port"] == 8000
    assert kwargs["reload"] is True
    assert kwargs["log_level"] == "debug"


# ---------------------------------------------------------------------------
# env var setdefault (already-set env vars are NOT overwritten)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_env_host_not_overwritten_if_already_set():
    with patch.object(sys, "argv", ["gateway", "--host", "1.2.3.4"]):
        with patch.dict(os.environ, {"GATEWAY_HOST": "already-set"}, clear=False):
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert os.environ.get("GATEWAY_HOST") == "already-set"


@pytest.mark.unit
def test_main_env_port_not_overwritten_if_already_set():
    with patch.object(sys, "argv", ["gateway", "--port", "9999"]):
        with patch.dict(os.environ, {"GATEWAY_PORT": "1234"}, clear=False):
            with patch("uvicorn.run"):
                import importlib, gateway.__main__ as gm
                importlib.reload(gm)
                gm.main()
                assert os.environ.get("GATEWAY_PORT") == "1234"


# ---------------------------------------------------------------------------
# uvicorn.run is called exactly once
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_uvicorn_called_once():
    mock_run = _run_main([])
    assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# __main__ guard (module-level if __name__ == "__main__")
# Verify the guard exists and calls main()
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dunder_main_guard_calls_main():
    """Executing the module as __main__ triggers main()."""
    with patch.object(sys, "argv", ["gateway"]):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("GATEWAY_HOST", "GATEWAY_PORT", "GATEWAY_DEBUG"):
                os.environ.pop(key, None)
            with patch("uvicorn.run") as mock_run:
                # Run via runpy to exercise the if __name__ == "__main__" block
                import runpy
                runpy.run_module("gateway.__main__", run_name="__main__", alter_sys=False)
                assert mock_run.call_count == 1
