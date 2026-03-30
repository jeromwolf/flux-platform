"""Tests for gateway/routes/websocket.py — WSRoute and get_ws_routes()."""
from __future__ import annotations

import pytest

from gateway.routes.websocket import WSRoute, get_ws_routes


# ---------------------------------------------------------------------------
# WSRoute dataclass creation
# ---------------------------------------------------------------------------


class TestWSRouteCreation:
    """TC-WR: WSRoute frozen dataclass construction and field validation."""

    @pytest.mark.unit
    def test_tc_wr01_default_path_is_ws(self):
        """TC-WR01: Default path is '/ws'."""
        r = WSRoute()
        assert r.path == "/ws"

    @pytest.mark.unit
    def test_tc_wr02_default_require_auth_is_false(self):
        """TC-WR02: Default require_auth is False."""
        r = WSRoute()
        assert r.require_auth is False

    @pytest.mark.unit
    def test_tc_wr03_default_max_connections_is_1000(self):
        """TC-WR03: Default max_connections is 1000."""
        r = WSRoute()
        assert r.max_connections == 1000

    @pytest.mark.unit
    def test_tc_wr04_custom_path_stored(self):
        """TC-WR04: Custom path is stored correctly."""
        r = WSRoute(path="/ws/chat")
        assert r.path == "/ws/chat"

    @pytest.mark.unit
    def test_tc_wr05_custom_require_auth_stored(self):
        """TC-WR05: require_auth=True is stored correctly."""
        r = WSRoute(require_auth=True)
        assert r.require_auth is True

    @pytest.mark.unit
    def test_tc_wr06_custom_max_connections_stored(self):
        """TC-WR06: Custom max_connections is stored correctly."""
        r = WSRoute(max_connections=50)
        assert r.max_connections == 50

    @pytest.mark.unit
    def test_tc_wr07_frozen_dataclass_immutable(self):
        """TC-WR07: WSRoute is frozen — mutation raises FrozenInstanceError."""
        r = WSRoute()
        with pytest.raises((AttributeError, TypeError)):
            r.path = "/new"  # type: ignore[misc]

    @pytest.mark.unit
    def test_tc_wr08_equality_same_fields(self):
        """TC-WR08: Two WSRoutes with identical fields are equal."""
        r1 = WSRoute(path="/ws", require_auth=False, max_connections=1000)
        r2 = WSRoute(path="/ws", require_auth=False, max_connections=1000)
        assert r1 == r2

    @pytest.mark.unit
    def test_tc_wr09_inequality_different_path(self):
        """TC-WR09: Two WSRoutes with different paths are not equal."""
        r1 = WSRoute(path="/ws/a")
        r2 = WSRoute(path="/ws/b")
        assert r1 != r2

    @pytest.mark.unit
    def test_tc_wr10_hashable_usable_in_set(self):
        """TC-WR10: WSRoute (frozen) is hashable and can be stored in a set."""
        r1 = WSRoute(path="/ws")
        r2 = WSRoute(path="/ws")
        r3 = WSRoute(path="/ws/other")
        s = {r1, r2, r3}
        assert len(s) == 2


# ---------------------------------------------------------------------------
# get_ws_routes()
# ---------------------------------------------------------------------------


class TestGetWsRoutes:
    """TC-GWR: get_ws_routes() returns expected route list."""

    @pytest.mark.unit
    def test_tc_gwr01_returns_list(self):
        """TC-GWR01: Return value is a list."""
        routes = get_ws_routes()
        assert isinstance(routes, list)

    @pytest.mark.unit
    def test_tc_gwr02_returns_at_least_one_route(self):
        """TC-GWR02: At least one route is returned."""
        routes = get_ws_routes()
        assert len(routes) >= 1

    @pytest.mark.unit
    def test_tc_gwr03_all_elements_are_wsroute(self):
        """TC-GWR03: All elements in the returned list are WSRoute instances."""
        routes = get_ws_routes()
        for route in routes:
            assert isinstance(route, WSRoute)

    @pytest.mark.unit
    def test_tc_gwr04_default_route_path_is_ws(self):
        """TC-GWR04: The first route has path '/ws'."""
        routes = get_ws_routes()
        assert routes[0].path == "/ws"

    @pytest.mark.unit
    def test_tc_gwr05_default_route_require_auth_false(self):
        """TC-GWR05: The first route has require_auth=False."""
        routes = get_ws_routes()
        assert routes[0].require_auth is False

    @pytest.mark.unit
    def test_tc_gwr06_default_route_max_connections_1000(self):
        """TC-GWR06: The first route has max_connections=1000."""
        routes = get_ws_routes()
        assert routes[0].max_connections == 1000

    @pytest.mark.unit
    def test_tc_gwr07_returns_fresh_list_each_call(self):
        """TC-GWR07: Each call returns a new list object (not shared state)."""
        routes1 = get_ws_routes()
        routes2 = get_ws_routes()
        assert routes1 is not routes2

    @pytest.mark.unit
    def test_tc_gwr08_all_paths_start_with_slash(self):
        """TC-GWR08: All route paths start with '/'."""
        routes = get_ws_routes()
        for route in routes:
            assert route.path.startswith("/"), f"Path '{route.path}' does not start with '/'"

    @pytest.mark.unit
    def test_tc_gwr09_no_duplicate_paths(self):
        """TC-GWR09: No two routes share the same path."""
        routes = get_ws_routes()
        paths = [r.path for r in routes]
        assert len(paths) == len(set(paths)), "Duplicate paths found in ws routes"

    @pytest.mark.unit
    def test_tc_gwr10_max_connections_positive(self):
        """TC-GWR10: All routes have max_connections > 0."""
        routes = get_ws_routes()
        for route in routes:
            assert route.max_connections > 0, (
                f"Route '{route.path}' has non-positive max_connections"
            )
