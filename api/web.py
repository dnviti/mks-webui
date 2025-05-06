# api/web.py
"""HTML front-end for the Ghost-6 printer service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core import crud

from core.driver.mkswifi import MKSPrinter

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Dependency: reuse the helpers from api.routes
# ---------------------------------------------------------------------------
from api.printers import _get_resources   # pylint: disable=wrong-import-position

@router.get("/", response_class=HTMLResponse, tags=["Frontend"], name="live_status")
async def dashboard(
    request: Request,
    resources: tuple[MKSPrinter, asyncio.Lock] = Depends(_get_resources),
) -> HTMLResponse:
    """
    Render an HTML dashboard (Jinja template) with the latest printer data.
    The template also loads JS that re-polls the **/printer/status** JSON
    endpoint every few seconds and updates the DOM.
    """
    printer, lock = resources
    async with lock:
        try:
            snapshot: Dict[str, Any] = await printer.poll()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    if not snapshot:
        snapshot = printer.latest or {}

    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,   # mandatory for Jinja2Templates
            "data": snapshot,
        },
    )

@router.get("/printers", response_class=HTMLResponse, tags=["Frontend"], name="printers")
def printer_page(request: Request, db: Session = Depends(get_db)):
    printers = crud.list_printers(db)
    return templates.TemplateResponse("printers.html", {"request": request,
                                                        "printers": printers})

@router.get("/history", response_class=HTMLResponse, tags=["Frontend"], name="history")
async def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})

@router.get("/files", response_class=HTMLResponse, tags=["Frontend"], name="files")
async def files(request: Request):
    return templates.TemplateResponse("files.html", {"request": request})

@router.get("/settings", response_class=HTMLResponse, tags=["Frontend"], name="settings")
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})
