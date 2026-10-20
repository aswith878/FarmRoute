"""FastAPI application entry point."""

import logging
from app.core.config import cors_origins

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Validate database configuration at startup without connecting to PostgreSQL.
from app.database import engine
from app.core.security import settings
from app.routes import auth, users, produce, buyer_requirements, transactions, matches, risk_tracking, routing_cases, processors, traceability

logger = logging.getLogger(__name__)

settings()  # Fail clearly when signing configuration is missing or invalid.

app = FastAPI(title="AgriRoute API", version="0.1.0")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(produce.router)
app.include_router(buyer_requirements.router)
app.include_router(transactions.router)
app.include_router(matches.router)
app.include_router(risk_tracking.router)
app.include_router(routing_cases.router)
app.include_router(processors.router)
app.include_router(traceability.router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if any(error["type"] == "enum" and error["loc"][-1] == "role" for error in errors):
        return JSONResponse(status_code=400, content={"detail": "Invalid role. Use FARMER, BUYER, PROCESSOR, or ADMIN."})
    # Exclude submitted input and context, which can contain sensitive values.
    safe_errors = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in errors]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("Database request failed; database details are suppressed.")
    return JSONResponse(status_code=500, content={"detail": "Database operation failed."})

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Report API availability; this does not check database connectivity."""
    return {"status": "ok", "service": "AgriRoute API"}


@app.get("/health/db", tags=["Health"])
def database_health() -> dict[str, str]:
    """Verify PostgreSQL connectivity without modifying database contents."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        # Never log exception details: driver messages can contain credentials.
        logger.error("Database health check failed: PostgreSQL connection unavailable.")
        raise HTTPException(
            status_code=500, detail="Database connection failed."
        ) from None

    return {
        "status": "ok",
        "database": "connected",
        "provider": "supabase-postgres",
    }
