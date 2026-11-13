"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-13 23:13:15.509147
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Native Postgres enum types. They are created and dropped explicitly (once each),
# so the column definitions use create_type=False. Autogenerate emits CREATE TYPE
# twice for order_status because both orders.status and
# admin_reminder_logs.status_at_reminder share it.
user_role_enum = postgresql.ENUM(
    'CUSTOMER', 'RESTAURANT_OWNER', 'DELIVERY_PARTNER',
    name='user_role', create_type=False,
)
order_status_enum = postgresql.ENUM(
    'PLACED', 'ACCEPTED', 'PREPARING', 'READY', 'ASSIGNED',
    'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'REFUNDED',
    name='order_status', create_type=False,
)
payment_status_enum = postgresql.ENUM(
    'pending', 'mock_paid', 'refunded',
    name='payment_status', create_type=False,
)
return_status_enum = postgresql.ENUM(
    'none', 'requested', 'approved', 'rejected',
    name='return_status', create_type=False,
)
ledger_type_enum = postgresql.ENUM(
    'PAYMENT', 'REFUND',
    name='ledger_type', create_type=False,
)
ENUM_TYPES = (
    user_role_enum,
    order_status_enum,
    payment_status_enum,
    return_status_enum,
    ledger_type_enum,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUM_TYPES:
        enum_type.create(bind, checkfirst=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', user_role_enum, nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', name='uq_users_email')
    )
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_table('restaurants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('cuisine', sa.String(length=60), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', name='uq_restaurants_owner_id')
    )
    op.create_index(op.f('ix_restaurants_name'), 'restaurants', ['name'], unique=False)
    op.create_table('menu_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=True),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('is_available', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('price > 0', name='ck_menu_items_price_positive'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_items_name'), 'menu_items', ['name'], unique=False)
    op.create_index(op.f('ix_menu_items_restaurant_id'), 'menu_items', ['restaurant_id'], unique=False)
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Integer(), nullable=False),
    sa.Column('delivery_partner_id', sa.Integer(), nullable=True),
    sa.Column('status', order_status_enum, nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('delivery_address', sa.String(length=300), nullable=False),
    sa.Column('delivery_phone', sa.String(length=20), nullable=False),
    sa.Column('payment_status', payment_status_enum, nullable=False),
    sa.Column('return_status', return_status_enum, nullable=False),
    sa.Column('return_reason', sa.Text(), nullable=True),
    sa.Column('return_requested_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('total_amount >= 0', name='ck_orders_total_amount_nonneg'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['delivery_partner_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_delivery_partner_id'), 'orders', ['delivery_partner_id'], unique=False)
    op.create_index(op.f('ix_orders_restaurant_id'), 'orders', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_orders_return_status'), 'orders', ['return_status'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_status_updated_at'), 'orders', ['status_updated_at'], unique=False)
    op.create_table('admin_reminder_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Integer(), nullable=False),
    sa.Column('status_at_reminder', order_status_enum, nullable=False),
    sa.Column('message', sa.String(length=300), nullable=False),
    sa.Column('is_resolved', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id', 'status_at_reminder', name='uq_admin_reminder_logs_order_status')
    )
    op.create_index(op.f('ix_admin_reminder_logs_order_id'), 'admin_reminder_logs', ['order_id'], unique=False)
    op.create_index(op.f('ix_admin_reminder_logs_restaurant_id'), 'admin_reminder_logs', ['restaurant_id'], unique=False)
    op.create_index('ix_admin_reminder_logs_restaurant_resolved', 'admin_reminder_logs', ['restaurant_id', 'is_resolved'], unique=False)
    op.create_table('order_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('menu_item_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.CheckConstraint('quantity BETWEEN 1 AND 99', name='ck_order_items_quantity_range'),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_menu_item_id'), 'order_items', ['menu_item_id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_table('payment_ledger',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('entry_type', ledger_type_enum, nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('transaction_ref', sa.String(length=40), nullable=False),
    sa.Column('card_last4', sa.String(length=4), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('transaction_ref', name='uq_payment_ledger_transaction_ref')
    )
    op.create_index(op.f('ix_payment_ledger_order_id'), 'payment_ledger', ['order_id'], unique=False)
    op.create_table('reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_reviews_rating_range'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id', name='uq_reviews_order_id')
    )
    op.create_index(op.f('ix_reviews_customer_id'), 'reviews', ['customer_id'], unique=False)
    op.create_index(op.f('ix_reviews_restaurant_id'), 'reviews', ['restaurant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reviews_restaurant_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_customer_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_payment_ledger_order_id'), table_name='payment_ledger')
    op.drop_table('payment_ledger')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_menu_item_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index('ix_admin_reminder_logs_restaurant_resolved', table_name='admin_reminder_logs')
    op.drop_index(op.f('ix_admin_reminder_logs_restaurant_id'), table_name='admin_reminder_logs')
    op.drop_index(op.f('ix_admin_reminder_logs_order_id'), table_name='admin_reminder_logs')
    op.drop_table('admin_reminder_logs')
    op.drop_index(op.f('ix_orders_status_updated_at'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_return_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_restaurant_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_delivery_partner_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_created_at'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_menu_items_restaurant_id'), table_name='menu_items')
    op.drop_index(op.f('ix_menu_items_name'), table_name='menu_items')
    op.drop_table('menu_items')
    op.drop_index(op.f('ix_restaurants_name'), table_name='restaurants')
    op.drop_table('restaurants')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_table('users')

    bind = op.get_bind()
    for enum_type in reversed(ENUM_TYPES):
        enum_type.drop(bind, checkfirst=True)
