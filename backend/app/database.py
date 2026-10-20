"""PostgreSQL engine and request-scoped SQLAlchemy sessions."""

import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is missing. Copy backend/.env.example to backend/.env "
        "and set your PostgreSQL connection URL."
    )

try:
    parsed_url = make_url(database_url)
    # Keep the DB-API consistent with psycopg2-binary from requirements.txt.
    # SQLAlchemy 2.1 may otherwise resolve plain `postgresql://` to psycopg 3.
    if parsed_url.drivername == "postgresql":
        parsed_url = parsed_url.set(drivername="postgresql+psycopg2")
    if parsed_url.drivername != "postgresql+psycopg2":
        raise ValueError("Unsupported database driver")
    # `pgbouncer=true` is a Prisma hint, not a libpq/psycopg2 option. The
    # transaction-mode pooler is selected by the connection host and port.
    connection_query = dict(parsed_url.query)
    connection_query.pop("pgbouncer", None)
    parsed_url = parsed_url.set(query=connection_query)
    engine = create_engine(parsed_url, pool_pre_ping=True)
except (ArgumentError, ValueError, SQLAlchemyError, ImportError):
    # Do not include the URL or underlying exception, which may contain secrets.
    raise RuntimeError(
        "Unable to configure PostgreSQL. Check DATABASE_URL in backend/.env "
        "(postgresql://username:password@localhost:5432/agriroute) and install "
        "backend/requirements.txt. URL-encode special characters in credentials."
    ) from None

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Supabase's session-mode pooler can be used for schema migrations while the
# application uses the transaction-mode pooler. Reuse the application engine
# when no separate migration URL is configured.
migration_database_url = os.getenv("DIRECT_URL", "").strip()
if migration_database_url:
    try:
        migration_parsed_url = make_url(migration_database_url)
        if migration_parsed_url.drivername == "postgresql":
            migration_parsed_url = migration_parsed_url.set(drivername="postgresql+psycopg2")
        if migration_parsed_url.drivername != "postgresql+psycopg2":
            raise ValueError("Unsupported database driver")
        migration_query = dict(migration_parsed_url.query)
        migration_query.pop("pgbouncer", None)
        migration_parsed_url = migration_parsed_url.set(query=migration_query)
        migration_engine = create_engine(migration_parsed_url, pool_pre_ping=True)
    except (ArgumentError, ValueError, SQLAlchemyError, ImportError):
        raise RuntimeError(
            "Unable to configure migration PostgreSQL. Check DIRECT_URL in backend/.env."
        ) from None
else:
    migration_engine = engine


class Base(DeclarativeBase):
    """Shared declarative base; schema changes are managed by Alembic."""


def get_db() -> Generator[Session, None, None]:
    """Yield a session, roll back failures, and always release resources."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
