"""Create workflow_executions table.

Revision ID: 002
Revises: 001
Create Date: 2026-05-07
"""
from typing import Sequence, Union
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id VARCHAR(12) PRIMARY KEY,
            workflow_id VARCHAR(8) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            trigger_type VARCHAR(20) NOT NULL DEFAULT 'manual',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            error_message TEXT DEFAULT '',
            node_results JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_executions_workflow_id ON workflow_executions(workflow_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_executions_status ON workflow_executions(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_executions_started_at ON workflow_executions(started_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workflow_executions;")
