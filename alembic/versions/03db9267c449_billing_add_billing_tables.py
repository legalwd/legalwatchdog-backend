"""billing: add billing tables

Revision ID: 03db9267c449
Revises: 00d2075dac2c
Create Date: 2025-11-25 01:45:27.948456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '03db9267c449'
down_revision: Union[str, Sequence[str], None] = '00d2075dac2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'billing_accounts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('stripe_customer_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('stripe_subscription_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('status', sa.Enum('TRIALING', 'ACTIVE', 'PAST_DUE', 'UNPAID', 'CANCELLED', 'BLOCKED', name='billingstatus'), nullable=False),
        sa.Column('trial_starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_billing_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column('current_price_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('default_payment_method_id', sa.Uuid(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_billing_org')
    )
    op.create_index(op.f('ix_billing_accounts_default_payment_method_id'), 'billing_accounts', ['default_payment_method_id'], unique=False)
    op.create_index(op.f('ix_billing_accounts_id'), 'billing_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_billing_accounts_organization_id'), 'billing_accounts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_billing_accounts_stripe_customer_id'), 'billing_accounts', ['stripe_customer_id'], unique=False)
    op.create_index(op.f('ix_billing_accounts_stripe_subscription_id'), 'billing_accounts', ['stripe_subscription_id'], unique=False)

    op.create_table(
        'billing_payment_methods',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('billing_account_id', sa.Uuid(), nullable=False),
        sa.Column('stripe_payment_method_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('card_brand', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('last4', sqlmodel.sql.sqltypes.AutoString(length=4), nullable=True),
        sa.Column('exp_month', sa.Integer(), nullable=True),
        sa.Column('exp_year', sa.Integer(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['billing_account_id'], ['billing_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_payment_methods_billing_account_id'), 'billing_payment_methods', ['billing_account_id'], unique=False)
    op.create_index(op.f('ix_billing_payment_methods_id'), 'billing_payment_methods', ['id'], unique=False)
    op.create_index(op.f('ix_billing_payment_methods_stripe_payment_method_id'), 'billing_payment_methods', ['stripe_payment_method_id'], unique=False)

    op.create_table(
        'billing_invoices',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('billing_account_id', sa.Uuid(), nullable=False),
        sa.Column('stripe_invoice_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('stripe_payment_intent_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('amount_due', sa.Integer(), nullable=False),
        sa.Column('amount_paid', sa.Integer(), nullable=False),
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'OPEN', 'PAID', 'VOID', 'PENDING', 'FAILED', 'REFUNDED', name='invoicestatus'), nullable=False),
        sa.Column('hosted_invoice_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('invoice_pdf_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['billing_account_id'], ['billing_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_invoices_billing_account_id'), 'billing_invoices', ['billing_account_id'], unique=False)
    op.create_index(op.f('ix_billing_invoices_id'), 'billing_invoices', ['id'], unique=False)
    op.create_index(op.f('ix_billing_invoices_stripe_invoice_id'), 'billing_invoices', ['stripe_invoice_id'], unique=False)
    op.create_index(op.f('ix_billing_invoices_stripe_payment_intent_id'), 'billing_invoices', ['stripe_payment_intent_id'], unique=False)

    op.create_foreign_key(
        "fk_billing_accounts_default_payment_method",
        source_table="billing_accounts",
        referent_table="billing_payment_methods",
        local_cols=["default_payment_method_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_billing_accounts_default_payment_method",
        "billing_accounts",
        type_="foreignkey",
    )

    op.drop_index(op.f('ix_billing_invoices_stripe_payment_intent_id'), table_name='billing_invoices')
    op.drop_index(op.f('ix_billing_invoices_stripe_invoice_id'), table_name='billing_invoices')
    op.drop_index(op.f('ix_billing_invoices_id'), table_name='billing_invoices')
    op.drop_index(op.f('ix_billing_invoices_billing_account_id'), table_name='billing_invoices')
    op.drop_table('billing_invoices')
    op.drop_index(op.f('ix_billing_payment_methods_stripe_payment_method_id'), table_name='billing_payment_methods')
    op.drop_index(op.f('ix_billing_payment_methods_id'), table_name='billing_payment_methods')
    op.drop_index(op.f('ix_billing_payment_methods_billing_account_id'), table_name='billing_payment_methods')
    op.drop_table('billing_payment_methods')
    op.drop_index(op.f('ix_billing_accounts_stripe_subscription_id'), table_name='billing_accounts')
    op.drop_index(op.f('ix_billing_accounts_stripe_customer_id'), table_name='billing_accounts')
    op.drop_index(op.f('ix_billing_accounts_organization_id'), table_name='billing_accounts')
    op.drop_index(op.f('ix_billing_accounts_id'), table_name='billing_accounts')
    op.drop_index(op.f('ix_billing_accounts_default_payment_method_id'), table_name='billing_accounts')
    op.drop_table('billing_accounts')
