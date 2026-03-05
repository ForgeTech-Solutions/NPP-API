"""FastAPI main application."""
import logging
import logging.config
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.auth.routes import router as auth_router
from app.medicaments.routes import router as medicaments_router
from app.importer.routes import router as import_router
from app.db.session import engine
from app.db.base import Base
from app.auth.models import User
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
    
    async with engine.begin() as conn:
        if os.environ.get("RECREATE_TABLES", "").lower() == "true":
            logger.warning("RECREATE_TABLES=true: Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Tables dropped")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created/verified")
    
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
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Initial admin user created: {settings.ADMIN_EMAIL}")
        else:
            logger.info(f"Admin user already exists: {settings.ADMIN_EMAIL}")
    
    yield
    
    await engine.dispose()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API pour la nomenclature nationale des produits pharmaceutiques à usage humain.\n\n"
        "## Fonctionnalités\n"
        "- **Authentification** JWT (Admin / Lecteur)\n"
        "- **Import** multi-feuilles Excel (Nomenclature, Non Renouvelés, Retraits)\n"
        "- **Recherche** full-text sur DCI, nom de marque, code, laboratoire\n"
        "- **Export CSV** avec filtres\n"
        "- **Dashboard** statistiques enrichies\n"
        "- **Nettoyage** automatique des doublons\n"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Check API health status with last import information."""
    from app.db.session import AsyncSessionLocal
    from app.models.import_log import ImportLog
    from sqlalchemy import select
    
    response = {
        "status": "ok",
        "version": settings.APP_VERSION,
        "derniere_mise_a_jour": None
    }
    
    # Get last successful import
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ImportLog)
                .where(ImportLog.end_time.is_not(None))
                .order_by(ImportLog.end_time.desc())
                .limit(1)
            )
            last_import = result.scalar_one_or_none()
            
            if last_import:
                response["derniere_mise_a_jour"] = last_import.version_nomenclature
    except Exception:
        # If database not ready or error, just return basic health
        pass
    
    return response


# Include routers
app.include_router(auth_router)
app.include_router(medicaments_router)
app.include_router(import_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
