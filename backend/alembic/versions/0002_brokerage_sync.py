"""brokerage sync metadata

Revision ID: 0002_brokerage_sync
Revises: 0001_initial_schema
Create Date: 2026-03-17 16:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_brokerage_sync"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("sync_provider", sa.String(length=32), nullable=True))
    op.add_column("accounts", sa.Column("sync_external_id", sa.String(length=128), nullable=True))
    op.add_column("accounts", sa.Column("sync_authorization_id", sa.String(length=128), nullable=True))
    op.add_column("accounts", sa.Column("sync_status", sa.String(length=32), nullable=True))
    op.add_column("accounts", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.add_column("accounts", sa.Column("last_sync_error", sa.Text(), nullable=True))
    op.create_index(op.f("ix_accounts_sync_external_id"), "accounts", ["sync_external_id"], unique=False)

    op.add_column("holdings", sa.Column("sync_provider", sa.String(length=32), nullable=True))
    op.add_column("holdings", sa.Column("sync_external_id", sa.String(length=128), nullable=True))
    op.add_column("holdings", sa.Column("synced_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_holdings_sync_external_id"), "holdings", ["sync_external_id"], unique=False)

    op.add_column("transactions", sa.Column("sync_provider", sa.String(length=32), nullable=True))
    op.add_column("transactions", sa.Column("sync_external_id", sa.String(length=128), nullable=True))
    op.add_column("transactions", sa.Column("synced_at", sa.DateTime(), nullable=True))
    op.create_index(
        op.f("ix_transactions_sync_external_id"),
        "transactions",
        ["sync_external_id"],
        unique=False,
    )

    op.create_table(
        "brokerage_sync_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("local_profile_id", sa.String(length=64), nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=False),
        sa.Column("external_user_secret", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_portal_url", sa.Text(), nullable=True),
        sa.Column("last_portal_expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "local_profile_id", name="uq_brokerage_sync_provider_profile"),
    )


def downgrade() -> None:
    op.drop_table("brokerage_sync_users")

    op.drop_index(op.f("ix_transactions_sync_external_id"), table_name="transactions")
    op.drop_column("transactions", "synced_at")
    op.drop_column("transactions", "sync_external_id")
    op.drop_column("transactions", "sync_provider")

    op.drop_index(op.f("ix_holdings_sync_external_id"), table_name="holdings")
    op.drop_column("holdings", "synced_at")
    op.drop_column("holdings", "sync_external_id")
    op.drop_column("holdings", "sync_provider")

    op.drop_index(op.f("ix_accounts_sync_external_id"), table_name="accounts")
    op.drop_column("accounts", "last_sync_error")
    op.drop_column("accounts", "last_synced_at")
    op.drop_column("accounts", "sync_status")
    op.drop_column("accounts", "sync_authorization_id")
    op.drop_column("accounts", "sync_external_id")
    op.drop_column("accounts", "sync_provider")
