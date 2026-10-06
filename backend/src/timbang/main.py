"""FastAPI application factory for Tilas.

Entry point: `uvicorn timbang.main:app --reload` (from backend/).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from timbang.modules.audit.router import router as audit_router
from timbang.modules.procurement.router import router as procurement_router
from timbang.shared.core.config import get_settings
from timbang.shared.core.logging import setup_logging
from timbang.shared.core.middleware import limiter, register_middleware


def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured 429 JSON response with Retry-After header when available."""
    retry_after: str | None = None
    if isinstance(exc, RateLimitExceeded):
        # slowapi stores the retry-after value on the exception
        retry_after = getattr(exc, "retry_after", None)

    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "detail": str(exc)},
        headers=headers,
    )


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    register_middleware(app)

    # SlowAPIMiddleware reads the limiter from app.state.limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

    app.include_router(procurement_router, prefix="/api/v1/procurement")
    app.include_router(audit_router, prefix="/api/v1/audit")

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        # /health is intentionally NOT rate-limited (uptime checks must always pass)
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
