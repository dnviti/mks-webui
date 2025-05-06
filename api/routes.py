# api/routes.py
"""HTTP endpoints for the Ghost-6 printer service."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.driver.mkswifi import MKSPrinter

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _get_resources(request: Request) -> tuple[MKSPrinter, asyncio.Lock]:
    """
    Fetch the shared ``(printer, lock)`` created in main.py.

    Returns
    -------
    (MKSPrinter, asyncio.Lock)

    Raises
    ------
    HTTPException(503) if startup failed.
    """
    printer: MKSPrinter | None = getattr(request.app.state, "printer", None)
    lock: asyncio.Lock | None = getattr(request.app.state, "printer_lock", None)
    if printer is None or lock is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Printer not connected",
        )
    return printer, lock


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/printer/raw/temp", 
    response_model=str,
    tags=["Printer"],
)
async def printer_status(
    resources: tuple[MKSPrinter, asyncio.Lock] = Depends(_get_resources),
) -> str:
    """
    Current printer temps in RAW.
    T:31 /0 B:27 /0 T0:31 /0 T1:0 /0 @:0 B@:0
    """
    printer, lock = resources
    async with lock:
        try:
            fresh = await printer.send(printer.GCodes.TEMP_QUERY)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    return fresh or printer.latest

@router.get(
    "/printer/status",
    response_model=Dict[str, Any],
    tags=["Printer"],
)
async def printer_status(
    resources: tuple[MKSPrinter, asyncio.Lock] = Depends(_get_resources),
) -> Dict[str, Any]:
    """
    Current printer snapshot in JSON.

    The structure mirrors :py:meth:`core.driver.mkswifi.MKSPrinter.poll`::

        {
          "temps":   {"T": 205.3, "Tset": 210.0, "B": 60.1, "Bset": 60.0},
          "progress": 37,
          "elapsed": "00:28:43",
          "state":   "PRINTING",
          "stamp":   "2025-05-06T11:32:10"
        }
    """
    printer, lock = resources
    async with lock:
        try:
            fresh = await printer.poll()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    return fresh or printer.latest
