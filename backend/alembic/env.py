"""Use the application's engine and complete model metadata for migrations."""
import logging

from alembic import context
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, migration_engine
import app.models  # noqa: F401 -- registers every model

logger = logging.getLogger("alembic.runtime.migration")
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
    except SQLAlchemyError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        # Log only non-sensitive diagnostic metadata; driver messages and URLs can contain credentials.
        logger.error("Migration database operation failed (%s, SQLSTATE=%s).", type(exc).__name__, sqlstate or "unavailable")
        raise RuntimeError("Migration database operation failed. Check connectivity, permissions, and schema compatibility; credentials are not logged.") from None
