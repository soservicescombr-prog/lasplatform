# netguard/backend/app/main.py
"""
NetGuard - Entry point da aplicação FastAPI.
Network Security & Monitoring Platform.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.database import init_db, async_session
from app.api.v1.router import api_router
from app.services.auth_service import AuthService
from app.services.syslog_service import syslog_receiver
from app.services.inventory_service import backfill_device_inventory

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🛡️  NetGuard v{} starting...", settings.APP_VERSION)

    # Create tables
    await init_db()
    logger.info("✅ Database tables verified")

    # Create initial admin if no users exist
    async with async_session() as db:
        service = AuthService(db)
        admin = await service.create_initial_admin()
        if admin:
            logger.info(
                "🔑 Admin padrão criado: admin / admin123 — TROQUE A SENHA!"
            )
        inventory_created = await backfill_device_inventory(db)
        if inventory_created:
            logger.info("📦 {} dispositivo(s) adicionados ao inventário", inventory_created)
        await db.commit()

    syslog_task = None
    if settings.SYSLOG_ENABLED:
        syslog_receiver.host = settings.SYSLOG_HOST
        syslog_receiver.port = settings.SYSLOG_PORT
        syslog_receiver.udp_enabled = settings.SYSLOG_UDP_ENABLED
        syslog_receiver.tcp_enabled = settings.SYSLOG_TCP_ENABLED
        syslog_task = asyncio.create_task(syslog_receiver.start())
        logger.info(
            "Syslog configured: listen {}:{}, advertised port {} (UDP={}, TCP={})",
            settings.SYSLOG_HOST, settings.SYSLOG_PORT, settings.SYSLOG_EXTERNAL_PORT,
            settings.SYSLOG_UDP_ENABLED, settings.SYSLOG_TCP_ENABLED,
        )

    logger.info("🚀 NetGuard ready at http://{}:{}", settings.HOST, settings.PORT)

    yield

    if syslog_task:
        syslog_receiver.stop()
        syslog_task.cancel()
        with suppress(asyncio.CancelledError):
            await syslog_task
    logger.info("🛑 NetGuard shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router)


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
