"""add use_ssl to smtp_configs

Revision ID: a1b2c3d4e5f6
Revises: 9f878a662677
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9f878a662677'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'smtp_configs',
        sa.Column('use_ssl', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('smtp_configs', 'use_ssl')
