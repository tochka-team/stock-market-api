"""Add linking fields to transactions table

Revision ID: 0081b8efa793
Revises: a9152c40824d
Create Date: 2025-05-26 07:44:32.336170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0081b8efa793'
down_revision: Union[str, None] = 'a9152c40824d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('balances', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.NUMERIC(),
               type_=sa.UUID(),
               existing_nullable=False)

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.NUMERIC(),
               type_=sa.UUID(),
               existing_nullable=False)
        batch_op.alter_column('user_id',
               existing_type=sa.NUMERIC(),
               type_=sa.UUID(),
               existing_nullable=False)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('buy_order_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('sell_order_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('buyer_user_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('seller_user_id', sa.UUID(), nullable=True))
        batch_op.alter_column('id',
               existing_type=sa.NUMERIC(),
               type_=sa.UUID(),
               existing_nullable=False)
        batch_op.create_index(batch_op.f('ix_transactions_buy_order_id'), ['buy_order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_buyer_user_id'), ['buyer_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_sell_order_id'), ['sell_order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_seller_user_id'), ['seller_user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.NUMERIC(),
               type_=sa.UUID(),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.UUID(),
               type_=sa.NUMERIC(),
               existing_nullable=False)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transactions_seller_user_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_sell_order_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_buyer_user_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_buy_order_id'))
        batch_op.alter_column('id',
               existing_type=sa.UUID(),
               type_=sa.NUMERIC(),
               existing_nullable=False)
        batch_op.drop_column('seller_user_id')
        batch_op.drop_column('buyer_user_id')
        batch_op.drop_column('sell_order_id')
        batch_op.drop_column('buy_order_id')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.UUID(),
               type_=sa.NUMERIC(),
               existing_nullable=False)
        batch_op.alter_column('id',
               existing_type=sa.UUID(),
               type_=sa.NUMERIC(),
               existing_nullable=False)

    with op.batch_alter_table('balances', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.UUID(),
               type_=sa.NUMERIC(),
               existing_nullable=False)

    # ### end Alembic commands ###
