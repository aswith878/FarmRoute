"""Use the application's engine and complete model metadata for migrations."""
from alembic import context
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, migration_engine
import app.models  # noqa: F401 -- registers every model

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Never autogenerate deletion of unrelated existing Supabase tables.
    if type_ == "table":
        return name in target_metadata.tables
    return True


if context.is_offline_mode():
    context.configure(
        url=migration_engine.url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    try:
        with migration_engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, include_name=include_name, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError:
        raise RuntimeError("Migration database operation failed. Check connectivity, permissions, and schema compatibility; credentials are not logged.") from None
