"""Add email to officers table and make badge_number optional

Revision ID: 002_officer_email
Revises: 001_initial
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_officer_email"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add email column as nullable initially for backfill
    op.add_column("officers", sa.Column("email", sa.String(255), nullable=True))

    # 2. Backfill existing demo officers by badge_number
    op.execute(
        "UPDATE officers SET email = 'rajesh.sharma@nic.in' WHERE badge_number = 'LM-DEL-042' AND email IS NULL"
    )
    op.execute(
        "UPDATE officers SET email = 'priya.verma@nic.in' WHERE badge_number = 'LM-MUM-108' AND email IS NULL"
    )
    op.execute(
        "UPDATE officers SET email = lower(replace(name, ' ', '.')) || '@nic.in' WHERE email IS NULL"
    )

    # 3. Alter email column to be NOT NULL
    op.alter_column("officers", "email", nullable=False)

    # 4. Add unique constraint on email
    op.create_unique_constraint("uq_officers_email", "officers", ["email"])

    # 5. Make badge_number nullable
    op.alter_column("officers", "badge_number", nullable=True)


def downgrade() -> None:
    op.alter_column("officers", "badge_number", nullable=False)
    op.drop_constraint("uq_officers_email", "officers", type_="unique")
    op.drop_column("officers", "email")
