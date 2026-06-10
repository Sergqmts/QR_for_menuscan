"""fix_orders_fk_cascade

Revision ID: f3c1a2d4e6b8
Revises: e5b89546f5c5
Create Date: 2026-06-10 10:22:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3c1a2d4e6b8'
down_revision: Union[str, Sequence[str], None] = 'e5b89546f5c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('orders_venue_id_fkey', 'orders', type_='foreignkey')
    op.drop_constraint('orders_table_id_fkey', 'orders', type_='foreignkey')
    op.create_foreign_key(None, 'orders', 'venues', ['venue_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'orders', 'tables', ['table_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.create_foreign_key(None, 'orders', 'venues', ['venue_id'], ['id'])
    op.create_foreign_key(None, 'orders', 'tables', ['table_id'], ['id'])
