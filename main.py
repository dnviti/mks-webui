# main.py
"""Application entry-point for the Ghost-6 printer API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core import models
from core.database import engine
from core.driver.mkswifi import MKSPrinter

from api import printers, web

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PRINTER_HOST = os.environ.get("PRINTER_HOST", "192.168.4.1")
PRINTER_PORT = int(os.environ.get("PRINTER_PORT", 8080))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 0.5))

# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Create one shared MKSPrinter and tear it down cleanly.
    Automatically create database on startup
    """
    models.Base.metadata.create_all(bind=engine)
    print("📦  DB ready")
    printer = MKSPrinter(PRINTER_HOST, PRINTER_PORT)
    await printer.connect()
    fastapi_app.state.printer = printer
    fastapi_app.state.printer_lock = asyncio.Lock()
    try:
        yield
    finally:
        print("👋  shutting down")
        await printer.close()

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ghost-6 printer API",
    version="1.0.1",
    description="REST façade around the MKS-Robin Wi-Fi protocol",
    lifespan=lifespan,
    # --- Swagger & OpenAPI endpoints ---------------------------------
    docs_url="/swagger",        # interactive UI
    redoc_url="/redoc",         # optional ReDoc
    openapi_url="/swagger.json" # raw schema for integrations
)

# Plug the routes defined in /api/*.py
app.include_router(printers.router)
app.include_router(web.router)

# Serve /static/* files (CSS & JS)
app.mount("/static", StaticFiles(directory="static"), name="static")
