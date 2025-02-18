"""add history records indexes

Revision ID: d3d11144457c
Revises: 8c1926493faf
Create Date: 2025-01-21 09:04:04.394099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3d11144457c'
down_revision: Union[str, None] = '8c1926493faf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index("idx_repository", "history_records", ["repository"])
    op.create_index("idx_commit", "history_records", ["commit_hash"])
    op.create_index("idx_timestamp", "history_records", ["timestamp"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("idx_timestamp", "history_records")
    op.drop_index("idx_commit", "history_records")
    op.drop_index("idx_repository", "history_records")
    # ### end Alembic commands ###
