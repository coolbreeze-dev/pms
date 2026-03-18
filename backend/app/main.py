from __future__ import annotations

import logging
from time import perf_counter
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import router
from app.core.auth import is_auth_exempt_path, parse_bearer_token, verify_token
from app.core.config import get_settings
from app.core.observability import ObservabilityStore
from app.db.session import init_db
from app.services.bootstrap import seed_reference_data
from app.services.jobs import ensure_scheduler_started
from app.db.session import SessionLocal


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )


configure_logging(get_settings().log_level)
logger = logging.getLogger("portfolio.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        seed_reference_data(session)
    if settings.enable_scheduler:
        ensure_scheduler_started()
    _app.state.observability = ObservabilityStore()
    logger.info(
        "app started environment=%s auth_enabled=%s scheduler_enabled=%s",
        settings.environment,
        settings.auth_enabled,
        settings.enable_scheduler,
    )
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512)
if get_settings().force_https:
    app.add_middleware(HTTPSRedirectMiddleware)
if get_settings().allowed_hosts and "*" not in get_settings().allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().allowed_hosts)
app.state.observability = ObservabilityStore()
app.include_router(router, prefix=get_settings().api_prefix)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    start = perf_counter()
    response = None
    try:
        if (
            request.method != "OPTIONS"
            and request.url.path.startswith(settings.api_prefix)
            and not is_auth_exempt_path(request.url.path, settings)
        ):
            expires_at = verify_token(parse_bearer_token(request.headers.get("Authorization")), settings)
            if settings.auth_enabled and expires_at is None:
                response = JSONResponse(status_code=401, content={"detail": "Authentication required."})
            else:
                request.state.auth_expires_at = expires_at
        if response is None:
            response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - start) * 1000
        app.state.observability.record(request.url.path, 500, duration_ms)
        logger.exception("request failed id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise

    duration_ms = (perf_counter() - start) * 1000
    app.state.observability.record(request.url.path, response.status_code, duration_ms)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.force_https:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
