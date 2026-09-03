"""Add category and meta columns to indicators, extend unit to VARCHAR(30)

Revision ID: 002
Revises: 001
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("indicators", "unit", type_=sa.String(30), existing_type=sa.String(20))
    op.add_column("indicators", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("indicators", sa.Column("meta", JSONB, nullable=True))
    op.create_index("idx_indicators_category", "indicators", ["category"])


def downgrade() -> None:
    op.drop_index("idx_indicators_category", table_name="indicators")
    op.drop_column("indicators", "meta")
    op.drop_column("indicators", "category")
    op.alter_column("indicators", "unit", type_=sa.String(20), existing_type=sa.String(30))
