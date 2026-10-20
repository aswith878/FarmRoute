"""add user credentials and case insensitive email uniqueness

Revision ID: e9e552718ba4
Revises: 3530a8eba68f
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e9e552718ba4'
down_revision: Union[str, Sequence[str], None] = '3530a8eba68f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive only: legacy credentials remain NULL; no existing row updates.
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('uq_users_email_lower', 'users', [sa.literal_column('lower(email)')], unique=True)


def downgrade() -> None:
    # Additive only: legacy credentials remain NULL; no existing row updates.
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'password_hash')
