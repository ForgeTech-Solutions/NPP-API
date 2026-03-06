"""FastAPI main application."""
import logging
import logging.config
import time
import secrets
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.auth.routes import router as auth_router
from app.medicaments.routes import router as medicaments_router
from app.importer.routes import router as import_router
from app.admin.routes import router as admin_router
from app.db.session import engine
from app.db.base import Base
from app.auth.models import User
from app.models.service_meta import ServiceMeta
from app.models.api_key import ApiKey  # noqa: F401 — ensure table is created
from app.core.security import get_password_hash

# ── Logging configuration ──────────────────────────────────────────────
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "format": "%(asctime)s | %(levelname)-8s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "nomenclature": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "nomenclature.import": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "nomenclature.crud": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "nomenclature.auth": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "sqlalchemy.engine": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("nomenclature")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: creates tables and initial admin user."""
    import os
    from sqlalchemy.exc import IntegrityError, ProgrammingError
    
    async with engine.begin() as conn:
        if os.environ.get("RECREATE_TABLES", "").lower() == "true":
            logger.warning("RECREATE_TABLES=true: Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Tables dropped")
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables created/verified")
        except (IntegrityError, ProgrammingError) as e:
            # Race condition: another worker already created the enum types / tables
            logger.info(f"Tables already exist (parallel worker race): {e.__class__.__name__}")
            await conn.rollback()
    
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                role="ADMIN",
                pack="DEVELOPPEUR",
                is_active=True,
                is_approved=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Initial admin user created: {settings.ADMIN_EMAIL}")
        else:
            logger.info(f"Admin user already exists: {settings.ADMIN_EMAIL}")

    # Store first deployment timestamp (set once, never overwritten)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        existing = await session.scalar(
            select(ServiceMeta).where(ServiceMeta.key == "first_deployed_at")
        )
        if not existing:
            session.add(ServiceMeta(
                key="first_deployed_at",
                value=datetime.utcnow().isoformat(),
            ))
            await session.commit()
            logger.info("Service first_deployed_at recorded")

    yield
    
    await engine.dispose()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    root_path=settings.ROOT_PATH,
    description=(
        "API pour la nomenclature nationale des produits pharmaceutiques à usage humain.\n\n"
        "## Fonctionnalités\n"
        "- **Système de packs** : FREE, PRO, INSTITUTIONNEL, DÉVELOPPEUR\n"
        "- **Rate limiting** : quota FREE (100 req/j, 1 000 req/mois)\n"
        "- **Authentification** JWT (Admin / Lecteur)\n"
        "- **Import** multi-feuilles Excel (Nomenclature, Non Renouvelés, Retraits)\n"
        "- **Recherche** full-text sur DCI, nom de marque, code, laboratoire\n"
        "- **Export CSV** avec filtres\n"
        "- **Dashboard** statistiques enrichies\n"
        "- **Nettoyage** automatique des doublons\n"
    ),
    lifespan=lifespan,
    docs_url=None,    # Disabled — served manually with Basic Auth below
    redoc_url=None,   # Disabled — served manually with Basic Auth below
    openapi_url=None,  # Disabled — served manually with Basic Auth below
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Protected documentation (HTTP Basic Auth) ──────────────────────────
docs_security = HTTPBasic()


def _verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(docs_security)):
    """Verify HTTP Basic credentials for /docs, /redoc, /openapi.json."""
    correct_user = secrets.compare_digest(credentials.username, settings.DOCS_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, settings.DOCS_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Accès à la documentation refusé",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi(credentials: HTTPBasicCredentials = Depends(_verify_docs_credentials)):
    """OpenAPI schema (protected)."""
    return app.openapi()


@app.get("/docs", include_in_schema=False)
async def swagger_ui(credentials: HTTPBasicCredentials = Depends(_verify_docs_credentials)):
    """Swagger UI (protected)."""
    openapi_url = f"{settings.ROOT_PATH}/openapi.json"
    return get_swagger_ui_html(openapi_url=openapi_url, title=f"{settings.APP_NAME} — Docs")


@app.get("/redoc", include_in_schema=False)
async def redoc_ui(credentials: HTTPBasicCredentials = Depends(_verify_docs_credentials)):
    """ReDoc (protected)."""
    openapi_url = f"{settings.ROOT_PATH}/openapi.json"
    return get_redoc_html(openapi_url=openapi_url, title=f"{settings.APP_NAME} — ReDoc")


# ── Request logging middleware ──────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path and duration."""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)"
    )
    return response


# Track current worker startup time
_startup_time = datetime.utcnow()


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Check API health status with database stats and uptime percentage."""
    from app.db.session import AsyncSessionLocal
    from app.models.import_log import ImportLog
    from app.models.service_meta import ServiceMeta
    from app.medicaments.models import Medicament
    from sqlalchemy import select, func
    import time as _time

    now = datetime.utcnow()
    uptime_seconds = int((now - _startup_time).total_seconds())
    uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"

    response = {
        "status": "ok",
        "version": settings.APP_VERSION,
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "uptime_percent": None,
        "db_latency_ms": None,
        "total_medicaments": None,
        "total_laboratoires": None,
        "derniere_mise_a_jour": None,
        "derniere_mise_a_jour_date": None,
    }

    try:
        async with AsyncSessionLocal() as session:
            t0 = _time.monotonic()

            # Total médicaments
            total_med = await session.scalar(select(func.count()).select_from(Medicament))

            # Total laboratoires distincts
            total_labs = await session.scalar(
                select(func.count(func.distinct(Medicament.laboratoire)))
            )

            # Latence DB
            db_latency_ms = round((_time.monotonic() - t0) * 1000, 2)

            # Premier démarrage du service (date de déploiement initial)
            first_deployed_row = await session.scalar(
                select(ServiceMeta).where(ServiceMeta.key == "first_deployed_at")
            )
            if first_deployed_row:
                first_deployed_at = datetime.fromisoformat(first_deployed_row.value)
                total_observed_seconds = max(1, (now - first_deployed_at).total_seconds())
                uptime_pct = round(min(uptime_seconds / total_observed_seconds * 100, 100.0), 2)
                response["uptime_percent"] = uptime_pct
                response["deployed_since"] = first_deployed_row.value

            # Dernier import réussi
            result = await session.execute(
                select(ImportLog)
                .where(ImportLog.end_time.is_not(None))
                .order_by(ImportLog.end_time.desc())
                .limit(1)
            )
            last_import = result.scalar_one_or_none()

            response["db_latency_ms"] = db_latency_ms
            response["total_medicaments"] = total_med or 0
            response["total_laboratoires"] = total_labs or 0
            if last_import:
                response["derniere_mise_a_jour"] = last_import.version_nomenclature
                response["derniere_mise_a_jour_date"] = (
                    last_import.end_time.isoformat() if last_import.end_time else None
                )
    except Exception as e:
        response["status"] = "degraded"
        response["db_error"] = str(e)

    return response


# ── Public pack catalog (no auth required) ─────────────────────────────
@app.get("/packs", tags=["Packs"], summary="Catalogue des packs (public)")
async def public_pack_catalog():
    """Liste publique des packs disponibles avec fonctionnalités et limites."""
    from app.core.packs import PACK_CATALOG
    return {"packs": list(PACK_CATALOG.values()), "total": len(PACK_CATALOG)}


# Include routers
app.include_router(auth_router)
app.include_router(medicaments_router)
app.include_router(import_router)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
