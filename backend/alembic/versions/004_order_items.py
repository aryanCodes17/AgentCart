"""Add order items for multi-item checkout."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_inr", sa.Numeric(12, 2), nullable=False),
    )

    op.create_index(
        "ix_order_items_order_id",
        "order_items",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
