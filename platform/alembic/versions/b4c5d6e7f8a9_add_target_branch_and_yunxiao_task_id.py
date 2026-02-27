"""add target_branch and yunxiao_task_id to tasks

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("target_branch", sa.String(length=200), nullable=True))
    op.add_column("tasks", sa.Column("yunxiao_task_id", sa.String(length=100), nullable=True))
    op.create_index("ix_tasks_yunxiao_task_id", "tasks", ["yunxiao_task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_yunxiao_task_id", table_name="tasks")
    op.drop_column("tasks", "yunxiao_task_id")
    op.drop_column("tasks", "target_branch")
