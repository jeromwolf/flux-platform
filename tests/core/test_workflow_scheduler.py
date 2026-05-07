"""Tests for workflow scheduler and webhook token manager."""
import pytest
import asyncio

from core.workflow.scheduler import WorkflowScheduler, WebhookTokenManager, ScheduleConfig


class TestScheduleConfig:
    def test_defaults(self):
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        assert config.enabled is True
        assert len(config.schedule_id) == 12
        assert config.workflow_id == "wf1"

    def test_frozen(self):
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        with pytest.raises(AttributeError):
            config.enabled = False

    def test_cron_expression_field(self):
        config = ScheduleConfig(workflow_id="wf1", cron_expression="*/5 * * * *")
        assert config.cron_expression == "*/5 * * * *"
        assert config.interval_seconds is None

    def test_description_field(self):
        config = ScheduleConfig(
            workflow_id="wf1",
            interval_seconds=60,
            description="Every minute",
        )
        assert config.description == "Every minute"


class TestWorkflowScheduler:
    @pytest.mark.asyncio
    async def test_add_schedule(self):
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        result = await scheduler.add_schedule(config)
        assert result.schedule_id == config.schedule_id

    @pytest.mark.asyncio
    async def test_add_schedule_no_trigger_raises(self):
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1")
        with pytest.raises(ValueError, match="Either cron_expression"):
            await scheduler.add_schedule(config)

    @pytest.mark.asyncio
    async def test_remove_schedule(self):
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)
        assert await scheduler.remove_schedule(config.schedule_id)
        assert not await scheduler.remove_schedule(config.schedule_id)

    @pytest.mark.asyncio
    async def test_enable_disable(self):
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)

        assert await scheduler.disable_schedule(config.schedule_id)
        s = scheduler.get_schedule(config.schedule_id)
        assert s is not None and not s.enabled

        assert await scheduler.enable_schedule(config.schedule_id)
        s = scheduler.get_schedule(config.schedule_id)
        assert s is not None and s.enabled

    @pytest.mark.asyncio
    async def test_list_schedules(self):
        scheduler = WorkflowScheduler()
        await scheduler.add_schedule(ScheduleConfig(workflow_id="wf1", interval_seconds=60))
        await scheduler.add_schedule(ScheduleConfig(workflow_id="wf2", interval_seconds=30))

        all_schedules = scheduler.list_schedules()
        assert len(all_schedules) == 2

        wf1_only = scheduler.list_schedules(workflow_id="wf1")
        assert len(wf1_only) == 1

    @pytest.mark.asyncio
    async def test_get_schedule(self):
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)
        result = scheduler.get_schedule(config.schedule_id)
        assert result is not None
        assert result.workflow_id == "wf1"

    def test_get_schedule_missing(self):
        scheduler = WorkflowScheduler()
        assert scheduler.get_schedule("nonexistent") is None

    @pytest.mark.asyncio
    async def test_enable_missing_returns_false(self):
        scheduler = WorkflowScheduler()
        assert not await scheduler.enable_schedule("nonexistent")

    @pytest.mark.asyncio
    async def test_disable_missing_returns_false(self):
        scheduler = WorkflowScheduler()
        assert not await scheduler.disable_schedule("nonexistent")

    @pytest.mark.asyncio
    async def test_start_stop(self):
        scheduler = WorkflowScheduler()
        await scheduler.add_schedule(ScheduleConfig(workflow_id="wf1", interval_seconds=60))
        await scheduler.start()
        assert scheduler.is_running
        assert scheduler.active_count == 1
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_start_only_enabled(self):
        """Disabled schedules should not spawn tasks."""
        scheduler = WorkflowScheduler()
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)
        await scheduler.disable_schedule(config.schedule_id)
        await scheduler.start()
        assert scheduler.active_count == 0
        await scheduler.stop()

    def test_cron_parser_interval(self):
        next_time = WorkflowScheduler._next_cron_time("*/5 * * * *")
        assert next_time is not None

    def test_cron_parser_daily(self):
        next_time = WorkflowScheduler._next_cron_time("0 9 * * *")
        assert next_time is not None

    def test_cron_parser_fallback(self):
        next_time = WorkflowScheduler._next_cron_time("complex expression")
        assert next_time is not None

    def test_is_running_default(self):
        scheduler = WorkflowScheduler()
        assert not scheduler.is_running

    def test_active_count_default(self):
        scheduler = WorkflowScheduler()
        assert scheduler.active_count == 0


class TestWebhookTokenManager:
    @pytest.mark.asyncio
    async def test_create_token(self):
        mgr = WebhookTokenManager()
        token = await mgr.create_token("wf1")
        assert len(token) == 24

    @pytest.mark.asyncio
    async def test_validate_token(self):
        mgr = WebhookTokenManager()
        token = await mgr.create_token("wf1")
        assert await mgr.validate_token("wf1", token)
        assert not await mgr.validate_token("wf2", token)
        assert not await mgr.validate_token("wf1", "wrong-token")

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        mgr = WebhookTokenManager()
        token = await mgr.create_token("wf1")
        assert await mgr.revoke_token(token)
        assert not await mgr.validate_token("wf1", token)
        assert not await mgr.revoke_token(token)  # already revoked

    @pytest.mark.asyncio
    async def test_list_tokens(self):
        mgr = WebhookTokenManager()
        t1 = await mgr.create_token("wf1")
        t2 = await mgr.create_token("wf1")
        tokens = await mgr.get_workflow_tokens("wf1")
        assert set(tokens) == {t1, t2}

    @pytest.mark.asyncio
    async def test_get_workflow_id(self):
        mgr = WebhookTokenManager()
        token = await mgr.create_token("wf1")
        assert await mgr.get_workflow_id(token) == "wf1"
        assert await mgr.get_workflow_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_multiple_workflows(self):
        mgr = WebhookTokenManager()
        t1 = await mgr.create_token("wf1")
        t2 = await mgr.create_token("wf2")
        assert await mgr.validate_token("wf1", t1)
        assert await mgr.validate_token("wf2", t2)
        assert not await mgr.validate_token("wf1", t2)
        assert not await mgr.validate_token("wf2", t1)

    @pytest.mark.asyncio
    async def test_get_workflow_tokens_empty(self):
        mgr = WebhookTokenManager()
        tokens = await mgr.get_workflow_tokens("nonexistent")
        assert tokens == []

    @pytest.mark.asyncio
    async def test_load_from_db_no_repo(self):
        """load_from_db is a no-op when no repo is configured."""
        mgr = WebhookTokenManager()
        await mgr.load_from_db()  # should not raise

    @pytest.mark.asyncio
    async def test_init_with_token_repo_none(self):
        """Token repo defaults to None, all operations still work in-memory."""
        mgr = WebhookTokenManager(token_repo=None)
        token = await mgr.create_token("wf1")
        assert await mgr.validate_token("wf1", token)
        assert await mgr.revoke_token(token)


class TestWorkflowSchedulerWithRepo:
    """Tests verifying scheduler PG persistence integration (mocked)."""

    @pytest.mark.asyncio
    async def test_add_schedule_persists_to_repo(self):
        """When schedule_repo is provided, add_schedule persists to it."""
        persisted = []

        class FakeRepo:
            async def create_schedule(self, schedule_dict):
                persisted.append(schedule_dict)
                return schedule_dict

            async def list_schedules(self, workflow_id=None):
                return []

        repo = FakeRepo()
        scheduler = WorkflowScheduler(schedule_repo=repo)
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)

        assert len(persisted) == 1
        assert persisted[0]["schedule_id"] == config.schedule_id
        assert persisted[0]["workflow_id"] == "wf1"

    @pytest.mark.asyncio
    async def test_remove_schedule_deletes_from_repo(self):
        deleted = []

        class FakeRepo:
            async def create_schedule(self, d):
                return d
            async def delete_schedule(self, sid):
                deleted.append(sid)
                return True
            async def list_schedules(self, workflow_id=None):
                return []

        repo = FakeRepo()
        scheduler = WorkflowScheduler(schedule_repo=repo)
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)
        await scheduler.remove_schedule(config.schedule_id)

        assert deleted == [config.schedule_id]

    @pytest.mark.asyncio
    async def test_enable_disable_updates_repo(self):
        updates = []

        class FakeRepo:
            async def create_schedule(self, d):
                return d
            async def update_enabled(self, sid, enabled):
                updates.append((sid, enabled))
                return True
            async def list_schedules(self, workflow_id=None):
                return []

        repo = FakeRepo()
        scheduler = WorkflowScheduler(schedule_repo=repo)
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        await scheduler.add_schedule(config)

        await scheduler.disable_schedule(config.schedule_id)
        await scheduler.enable_schedule(config.schedule_id)

        assert updates == [(config.schedule_id, False), (config.schedule_id, True)]

    @pytest.mark.asyncio
    async def test_start_loads_from_db(self):
        """start() should populate schedules from PG repo."""

        class FakeRepo:
            async def list_schedules(self, workflow_id=None):
                return [
                    {
                        "schedule_id": "db_sched_01",
                        "workflow_id": "wf_db",
                        "cron_expression": "",
                        "interval_seconds": 120,
                        "enabled": True,
                        "description": "from db",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ]

        repo = FakeRepo()
        scheduler = WorkflowScheduler(schedule_repo=repo)
        assert len(scheduler.list_schedules()) == 0

        await scheduler.start()
        assert len(scheduler.list_schedules()) == 1
        s = scheduler.get_schedule("db_sched_01")
        assert s is not None
        assert s.workflow_id == "wf_db"
        assert s.interval_seconds == 120
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_repo_error_does_not_crash_add(self):
        """PG persistence errors are caught — in-memory still works."""

        class FailRepo:
            async def create_schedule(self, d):
                raise RuntimeError("PG down")
            async def list_schedules(self, workflow_id=None):
                return []

        scheduler = WorkflowScheduler(schedule_repo=FailRepo())
        config = ScheduleConfig(workflow_id="wf1", interval_seconds=60)
        result = await scheduler.add_schedule(config)
        assert result.schedule_id == config.schedule_id
        # Still in memory
        assert scheduler.get_schedule(config.schedule_id) is not None


class TestWebhookTokenManagerWithRepo:
    """Tests verifying webhook PG persistence integration (mocked)."""

    @pytest.mark.asyncio
    async def test_create_token_persists(self):
        persisted = []

        class FakeRepo:
            async def create_token(self, token, workflow_id):
                persisted.append((token, workflow_id))
                return {"token": token, "workflow_id": workflow_id}

        mgr = WebhookTokenManager(token_repo=FakeRepo())
        token = await mgr.create_token("wf1")
        assert len(persisted) == 1
        assert persisted[0] == (token, "wf1")

    @pytest.mark.asyncio
    async def test_revoke_token_deletes_from_repo(self):
        revoked = []

        class FakeRepo:
            async def create_token(self, token, wf):
                return {}
            async def revoke_token(self, token):
                revoked.append(token)
                return True

        mgr = WebhookTokenManager(token_repo=FakeRepo())
        token = await mgr.create_token("wf1")
        await mgr.revoke_token(token)
        assert revoked == [token]

    @pytest.mark.asyncio
    async def test_validate_falls_through_to_repo(self):
        """If not in memory cache, validate checks PG."""

        class FakeRepo:
            async def create_token(self, token, wf):
                return {}
            async def validate_token(self, wf, token):
                return token == "pg_token" and wf == "wf_pg"

        mgr = WebhookTokenManager(token_repo=FakeRepo())
        # This token is only in PG, not in memory
        assert await mgr.validate_token("wf_pg", "pg_token")
        # After validation, it should be cached
        assert mgr._tokens.get("pg_token") == "wf_pg"

    @pytest.mark.asyncio
    async def test_get_workflow_id_falls_through_to_repo(self):
        """get_workflow_id checks PG when not in memory."""

        class FakeRepo:
            async def create_token(self, token, wf):
                return {}
            async def get_workflow_id(self, token):
                if token == "pg_tok":
                    return "wf_remote"
                return None

        mgr = WebhookTokenManager(token_repo=FakeRepo())
        assert await mgr.get_workflow_id("pg_tok") == "wf_remote"
        # After lookup, cached
        assert mgr._tokens.get("pg_tok") == "wf_remote"
        # Unknown token
        assert await mgr.get_workflow_id("unknown") is None

    @pytest.mark.asyncio
    async def test_get_workflow_tokens_from_repo(self):
        """When repo is available, get_workflow_tokens queries PG."""

        class FakeRepo:
            async def create_token(self, token, wf):
                return {}
            async def list_tokens(self, workflow_id):
                return ["tok_a", "tok_b"] if workflow_id == "wf1" else []

        mgr = WebhookTokenManager(token_repo=FakeRepo())
        tokens = await mgr.get_workflow_tokens("wf1")
        assert set(tokens) == {"tok_a", "tok_b"}

    @pytest.mark.asyncio
    async def test_repo_error_falls_back_to_memory(self):
        """PG errors during validate don't crash — falls back to False."""

        class FailRepo:
            async def create_token(self, token, wf):
                return {}
            async def validate_token(self, wf, token):
                raise RuntimeError("PG down")

        mgr = WebhookTokenManager(token_repo=FailRepo())
        # Not in memory and PG fails → False
        assert not await mgr.validate_token("wf1", "bad_token")
