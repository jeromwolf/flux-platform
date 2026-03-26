"""Create workflows and documents tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id          VARCHAR(8)   PRIMARY KEY,
            name        VARCHAR(255) NOT NULL DEFAULT 'Untitled Workflow',
            description TEXT         NOT NULL DEFAULT '',
            nodes       JSONB        NOT NULL DEFAULT '[]'::jsonb,
            edges       JSONB        NOT NULL DEFAULT '[]'::jsonb,
            viewport    JSONB        NOT NULL DEFAULT '{}'::jsonb,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id           VARCHAR(16)  PRIMARY KEY,
            filename     VARCHAR(512) NOT NULL,
            size         INTEGER      NOT NULL,
            content_type VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
            description  TEXT         NOT NULL DEFAULT '',
            status       VARCHAR(32)  NOT NULL DEFAULT 'uploaded',
            chunks       INTEGER      NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_workflows_updated_at ON workflows (updated_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS documents;")
    op.execute("DROP TABLE IF EXISTS workflows;")
