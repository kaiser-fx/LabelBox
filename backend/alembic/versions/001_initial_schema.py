"""Initial schema — all six core tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "officers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("badge_number", sa.String(50), unique=True, nullable=False),
        sa.Column("jurisdiction", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "inspection_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("officer_id", sa.String(), sa.ForeignKey("officers.id"), nullable=False),
        sa.Column("store_name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
    )

    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scan_id", sa.String(), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("field_type", sa.String(100), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("bounding_box", sa.Text(), nullable=True),
    )

    op.create_table(
        "violations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scan_id", sa.String(), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("rule_id", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
    )

    op.create_table(
        "rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("validation_function_ref", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rules")
    op.drop_table("violations")
    op.drop_table("extracted_fields")
    op.drop_table("scans")
    op.drop_table("inspection_sessions")
    op.drop_table("officers")
