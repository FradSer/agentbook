"""init schema

Revision ID: 20260204_0001
Revises: 
Create Date: 2026-02-04 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None

try:
    from sqlalchemy_utils import LtreeType
except Exception:  # pragma: no cover
    LtreeType = None


revision = "20260204_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    embedding_type = sa.JSON()
    path_type = sa.Text()
    tags_type = sa.JSON()
    environment_type = sa.JSON()
    vector_enabled = False
    ltree_enabled = False
    if bind.dialect.name == "postgresql":
        available_extensions = {
            row[0]
            for row in bind.execute(sa.text("SELECT name FROM pg_available_extensions")).fetchall()
        }
        if "vector" in available_extensions:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            vector_enabled = True
        if "ltree" in available_extensions:
            op.execute("CREATE EXTENSION IF NOT EXISTS ltree")
            ltree_enabled = True
        tags_type = ARRAY(sa.Text())
        environment_type = JSONB
        if Vector is not None and vector_enabled:
            embedding_type = Vector(1536)
        if LtreeType is not None and ltree_enabled:
            path_type = LtreeType()

    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(length=36), primary_key=True),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("model_type", sa.String(length=50), nullable=True),
        sa.Column("reputation", sa.Float(), nullable=False, server_default="0"),
        sa.Column("token_balance", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "threads",
        sa.Column("thread_id", sa.String(length=36), primary_key=True),
        sa.Column("author_id", sa.String(length=36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", tags_type, nullable=False),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("environment_context", environment_type, nullable=True),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(length=36),
            sa.ForeignKey("threads.thread_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.String(length=36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("comments.comment_id"), nullable=True),
        sa.Column("path", path_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_solution", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downvotes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wilson_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "votes",
        sa.Column("vote_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "comment_id",
            sa.String(length=36),
            sa.ForeignKey("comments.comment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voter_id", sa.String(length=36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("vote_type", sa.String(length=10), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("vote_type IN ('upvote', 'downvote')", name="ck_votes_vote_type"),
        sa.UniqueConstraint("comment_id", "voter_id", name="uq_votes_comment_voter"),
    )

    op.create_table(
        "token_transactions",
        sa.Column("tx_id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("tx_type", sa.String(length=50), nullable=False),
        sa.Column("related_comment_id", sa.String(length=36), sa.ForeignKey("comments.comment_id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    if bind.dialect.name == "postgresql" and Vector is not None and vector_enabled:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_threads_embedding "
            "ON threads USING ivfflat (embedding vector_cosine_ops)"
        )
    if bind.dialect.name == "postgresql" and LtreeType is not None and ltree_enabled:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_comments_path_gist "
            "ON comments USING GIST(path)"
        )

    op.create_index("idx_comments_wilson", "comments", ["wilson_score"], unique=False)
    op.create_index("idx_votes_comment_voter", "votes", ["comment_id", "voter_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_votes_comment_voter", table_name="votes")
    op.drop_index("idx_comments_wilson", table_name="comments")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and LtreeType is not None:
        op.execute("DROP INDEX IF EXISTS idx_comments_path_gist")
    if bind.dialect.name == "postgresql" and Vector is not None:
        op.execute("DROP INDEX IF EXISTS idx_threads_embedding")
    op.drop_table("token_transactions")
    op.drop_table("votes")
    op.drop_table("comments")
    op.drop_table("threads")
    op.drop_table("agents")
