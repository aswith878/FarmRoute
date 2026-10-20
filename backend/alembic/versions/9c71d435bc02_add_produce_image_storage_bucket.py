"""provision the AgriRoute public produce image bucket when running on Supabase

Revision ID: 9c71d435bc02
Revises: e9e552718ba4
"""
from typing import Sequence, Union

from alembic import op


revision: str = "9c71d435bc02"
down_revision: Union[str, Sequence[str], None] = "e9e552718ba4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Storage is a Supabase-managed schema. Keep ordinary PostgreSQL development
    # databases usable while provisioning the bucket on Supabase projects.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('storage.buckets') IS NOT NULL THEN
                INSERT INTO storage.buckets
                    (id, name, public, file_size_limit, allowed_mime_types)
                VALUES
                    ('agriroute-produce-images', 'agriroute-produce-images', TRUE,
                     5242880, ARRAY['image/png', 'image/jpeg', 'image/webp']::text[])
                ON CONFLICT (id) DO NOTHING;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Preserve bucket contents and settings; migration rollback must not delete
    # user-uploaded photos.
    pass
