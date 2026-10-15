"""add max_per_day to smtp_configs

Revision ID: 61993cb24a06
Revises: a1b2c3d4e5f6
Create Date: 2026-10-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '61993cb24a06'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 每天发送上限（滚动 24 小时），现有行为 NULL 即不限，行为不变
    op.add_column(
        'smtp_configs',
        sa.Column('max_per_day', sa.Integer(), nullable=True),
    )
    # 限流统计按 smtp_config_id + status + sent_at 查询窗口内已发送数量
    op.create_index(
        'idx_tasks_smtp_status_sent',
        'email_tasks',
        ['smtp_config_id', 'status', 'sent_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_tasks_smtp_status_sent', table_name='email_tasks')
    op.drop_column('smtp_configs', 'max_per_day')
