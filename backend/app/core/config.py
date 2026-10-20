"""Environment-backed application configuration with fail-closed validation."""

import os
from urllib.parse import urlsplit


def cors_origins() -> list[str]:
    """Return explicit browser origins; credentialed CORS must never use '*'."""
    configured = os.getenv("AGRIROUTE_CORS_ORIGINS", "http://localhost:5173")
    origins = []
    for value in configured.split(","):
        origin = value.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "AGRIROUTE_CORS_ORIGINS must be a comma-separated list of explicit HTTP(S) origins."
            )
        origins.append(f"{parsed.scheme}://{parsed.netloc}")
    if not origins:
        raise RuntimeError("AGRIROUTE_CORS_ORIGINS must contain at least one origin.")
    return list(dict.fromkeys(origins))
