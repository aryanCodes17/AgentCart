
"""Prevent multiple unresolved capture attempts per order."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_one_started_capture_per_order"
PREDICATE = sa.text("kind = 'capture' AND status = 'started'")


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "payment_attempts",
        ["order_id"],
        unique=True,
        sqlite_where=PREDICATE,
        postgresql_where=PREDICATE,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="payment_attempts")
