import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from app.core.config import Settings
from app.core.errors import AppError, ErrorEnvelope, error_response
from app.db.session import make_engine, session_factory
from app.modules.appraisals.router import router as appraisal_router
from app.modules.auth.router import router as auth_router
from app.modules.forms.router import router as form_router
from app.modules.help.router import router as help_router
from app.modules.hr.calibrations import router as calibration_router
from app.modules.hr.evaluations import router as evaluations_router
from app.modules.hr.router import router as hr_router
from app.modules.imports.router import router as import_router
from app.modules.notifications.service import deliver_pending
from app.modules.reviews.router import router as reviews_router
from app.modules.users.router import router as admin_router

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or scope["path"].startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        worker = asyncio.create_task(_mail_worker(application))
        try:
            yield
        finally:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            application.state.engine.dispose()

    async def _mail_worker(application):
        while True:
            try:
                await deliver_pending(application.state.sessions, application.state.settings)
            except Exception as exc:
                logger.warning("Mail notification worker iteration failed (%s)", type(exc).__name__)
            await asyncio.sleep(5)

    app = FastAPI(
        title="MyCareer API",
        version="0.1.0",
        lifespan=lifespan,
        responses={
            status: {"model": ErrorEnvelope} for status in [400, 401, 403, 404, 409, 422, 429, 500, 503]
        },
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings)
    app.state.sessions = session_factory(app.state.engine)
    hosts = sorted({urlsplit(o).hostname for o in settings.allowed_origins})
    if settings.environment == "test":
        hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") not in settings.allowed_origins:
                response = error_response(request, 403, "ORIGIN_REJECTED", "Request origin is not permitted.")
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if not request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' https://medimpactinternational.com; connect-src 'self'; "
                "font-src 'self'; object-src 'none'; base-uri 'self'; "
                "frame-ancestors 'none'; form-action 'self'"
            )
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return error_response(request, exc.status, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic error inputs can contain credentials; never serialize them.
        fields = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": "Invalid or unexpected value."}
            for e in exc.errors()
        ]
        return error_response(request, 422, "VALIDATION_ERROR", "Check the highlighted fields.", fields)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(
            request, exc.status_code, "REQUEST_REJECTED", "The request could not be completed."
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, _):
        return error_response(request, 503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable.")

    @app.exception_handler(Exception)
    async def unexpected_error(request, _):
        return error_response(
            request, 500, "INTERNAL_ERROR", "The request could not be completed. Please try again."
        )

    @app.get("/api/v1/health/live", tags=["Health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health/ready", tags=["Health"])
    def ready(request: Request) -> dict[str, str]:
        with request.app.state.engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "rolepolicy":
                raise AppError(503, "MIGRATION_REQUIRED", "Database migration is required.")
        return {"status": "ready"}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(appraisal_router, prefix="/api/v1")
    app.include_router(reviews_router, prefix="/api/v1")
    app.include_router(hr_router, prefix="/api/v1")
    app.include_router(form_router, prefix="/api/v1")
    app.include_router(import_router, prefix="/api/v1")
    app.include_router(evaluations_router, prefix="/api/v1")
    app.include_router(calibration_router, prefix="/api/v1")
    app.include_router(help_router, prefix="/api/v1")

    if settings.static_directory:
        static_root = Path(settings.static_directory)
        if not static_root.is_dir():
            raise RuntimeError(f"Configured static directory does not exist: {static_root}")
        app.mount("/", SPAStaticFiles(directory=static_root, html=True), name="frontend")
    return app
