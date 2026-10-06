import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException

from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import Clock, hash_password
from app.db.session import database
from app.integrations.email import SMTPMailer
from app.modules.auth.router import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("agrolab")


def error_response(request, status, code, message, retry_after=None):
    headers = {"Cache-Control": "no-store"}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
            }
        },
        headers=headers,
    )


def create_app(settings=None, *, engine=None, clock=None, mailer=None):
    settings = settings or Settings()
    owns_engine = engine is None
    if owns_engine:
        engine, factory = database(settings)
    else:
        factory = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owns_engine:
            engine.dispose()

    docs = settings.environment != "production"
    app = FastAPI(
        title="AgroLab API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.clock = clock or Clock()
    app.state.mailer = mailer or SMTPMailer(settings)
    app.state.dummy_hash = hash_password("dummy-password-never-used", settings.bcrypt_cost)

    @app.middleware("http")
    async def request_context(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        if (
            settings.environment == "production"
            and request.url.scheme != "https"
            and not request.url.path.startswith("/health/")
        ):
            response = error_response(request, 400, "HTTPS_REQUIRED", "Use uma conexão HTTPS.")
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if settings.environment == "production" and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return error_response(request, exc.status, exc.code, exc.message, exc.retry_after)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic errors inclui input; nunca serializar a senha/token de entrada.
        return error_response(request, 422, "VALIDATION_ERROR", "Verifique os campos informados.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, "HTTP_ERROR", "Requisição não disponível.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.error(
            "database_failure type=%s request_id=%s", type(exc).__name__, request.state.request_id
        )
        return error_response(
            request, 503, "DATABASE_UNAVAILABLE", "Serviço temporariamente indisponível."
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            "unexpected_failure type=%s request_id=%s", type(exc).__name__, request.state.request_id
        )
        return error_response(
            request, 500, "INTERNAL_ERROR", "Não foi possível concluir a solicitação."
        )

    @app.get("/health/live", tags=["Saúde"])
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Saúde"])
    def ready(request: Request):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return error_response(request, 503, "DATABASE_UNAVAILABLE", "Banco indisponível.")
        return {"status": "ready"}

    app.include_router(router)
    return app
