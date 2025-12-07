"""upgrade to uuid4 for items

Revision ID: 6661c50064ca
Revises: 47ad9c6c4a77
Create Date: 2025-12-07 17:01:21.590510

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6661c50064ca'
down_revision: Union[str, Sequence[str], None] = '47ad9c6c4a77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Drop old integer column (table must be empty)
    op.drop_column("found_items", "id")
    op.drop_column("lost_items", "id")

    # Create new UUID PK column
    op.add_column(
        "found_items",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False)
    )
    op.add_column(
        "lost_items",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False)
    )


def downgrade():
    # Reverse: drop UUID, add back integer PK
    op.drop_column("found_items", "id")
    op.drop_column("lost_items", "id")

    op.add_column(
        "found_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False)
    )
    op.add_column(
        "lost_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False)
    )
