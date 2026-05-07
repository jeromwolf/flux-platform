"""Create schedules and webhook_tokens tables.

Revision ID: 003
Revises: 002
Create Date: 2026-05-07
"""
from typing import Sequence, Union
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_schedules (
            schedule_id VARCHAR(12) PRIMARY KEY,
            workflow_id VARCHAR(8) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            cron_expression VARCHAR(100) DEFAULT '',
            interval_seconds INTEGER,
            enabled BOOLEAN DEFAULT TRUE,
            description TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_schedules_workflow_id ON workflow_schedules(workflow_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON workflow_schedules(enabled);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_tokens (
            token VARCHAR(24) PRIMARY KEY,
            workflow_id VARCHAR(8) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_tokens_workflow_id ON webhook_tokens(workflow_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_tokens;")
    op.execute("DROP TABLE IF EXISTS workflow_schedules;")
