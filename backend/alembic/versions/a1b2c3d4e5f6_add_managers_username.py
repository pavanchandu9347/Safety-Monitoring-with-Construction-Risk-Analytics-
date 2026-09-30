"""add managers.username (login identifier)

Revision ID: a1b2c3d4e5f6
Revises: 76075756b1f9
Create Date: 2026-09-30 12:00:00.000000

The login identifier is now the manager ``username`` (the former email-based
login remains a fallback). Existing rows are backfilled from the local part of
their email before the NOT NULL + unique constraints are applied.
"""

from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '76075756b1f9'
branch_labels = None
depends_on = None


def _backfill(connection):
    if connection.dialect.name == "postgresql":
        sql = (
            "UPDATE managers SET username = NULLIF(lower(split_part(email, '@', 1)), '') "
            "WHERE username IS NULL OR username = ''"
        )
    else:
        sql = (
            "UPDATE managers SET username = lower(substr(email, 1, instr(email, '@') - 1)) "
            "WHERE username IS NULL OR username = ''"
        )
    connection.execute(sa.text(sql))


def upgrade() -> None:
    op.add_column('managers', sa.Column('username', sa.String(), nullable=True))
    conn = op.get_bind()
    _backfill(conn)
    op.alter_column('managers', 'username', nullable=False)
    op.create_index(op.f('ix_managers_username'), 'managers', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_managers_username'), table_name='managers')
    op.drop_column('managers', 'username')