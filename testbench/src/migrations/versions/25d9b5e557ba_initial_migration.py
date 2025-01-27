"""Initial migration

Revision ID: 25d9b5e557ba
Revises:
Create Date: 2025-02-13 09:39:31.269772

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25d9b5e557ba"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS function")
    op.execute("CREATE SCHEMA IF NOT EXISTS configuration")

    # Create transaction table required by sqlalchemy-continuum
    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("remote_addr", sa.String(255)),
        sa.Column("issued_at", sa.DateTime, default=datetime.utcnow),
    )

    # Create configurations table
    op.create_table(
        "configurations",
        sa.Column("section", sa.String(), primary_key=True),
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("transaction_id", sa.Integer),  # Versioning column
        sa.Column("operation_type", sa.String(50)),  # Versioning column
        schema="configuration",
    )

    # Create functions table
    op.create_table(
        "functions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("transaction_id", sa.Integer),  # Versioning column
        sa.Column("operation_type", sa.String(50)),  # Versioning column
        schema="function",
    )

    # Create config history table
    op.create_table(
        "config_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
        schema="configuration",
    )

    # Create `configurations_version` table (🔹 Added `end_transaction_id`)
    op.create_table(
        "configurations_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("section", sa.String, nullable=False),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("transaction_id", sa.Integer, nullable=False),
        sa.Column(
            "end_transaction_id", sa.BigInteger, nullable=True
        ),  # 🔹 New column
        sa.Column("operation_type", sa.String(50), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String, nullable=True),
        schema="configuration",
    )

    # Create `functions_version` table
    op.create_table(
        "functions_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("transaction_id", sa.Integer, nullable=False),
        sa.Column("operation_type", sa.String(50), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String, nullable=True),
        schema="function",
    )


def downgrade():
    """Rollback migration: Drop tables and schemas"""
    op.drop_table("config_history", schema="configuration")
    op.drop_table("configurations_version", schema="configuration")
    op.drop_table("functions_version", schema="function")
    op.drop_table("configurations", schema="configuration")
    op.drop_table("functions", schema="function")
    op.drop_table("transaction")  # Drop `transaction` table

    op.execute("DROP SCHEMA IF EXISTS function CASCADE")
    op.execute("DROP SCHEMA IF EXISTS configuration CASCADE")
