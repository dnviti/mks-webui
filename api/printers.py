from typing import Dict, Any
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core import crud, schemas

from core.driver.mkswifi import MKSPrinter

router = APIRouter(prefix="/api/v1/printers", tags=["api.v1, printers"])

# Dependency  – one DB session / request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.PrinterOut, status_code=201)
def create(data: schemas.PrinterCreate, db: Session = Depends(get_db)):
    return crud.create_printer(db, data)

@router.get("/", response_model=list[schemas.PrinterOut])
def read_all(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.list_printers(db, skip, limit)

@router.get("/{pid}", response_model=schemas.PrinterOut)
def read_one(pid: int, db: Session = Depends(get_db)):
    db_item = crud.get_printer(db, pid)
    if not db_item:
        raise HTTPException(404, detail="Printer not found")
    return db_item

@router.put("/{pid}", response_model=schemas.PrinterOut)
def update(pid: int, data: schemas.PrinterUpdate, db: Session = Depends(get_db)):
    db_item = crud.get_printer(db, pid)
    if not db_item:
        raise HTTPException(404, detail="Printer not found")
    return crud.update_printer(db, db_item, data)

@router.delete("/{pid}", status_code=204)
def delete(pid: int, db: Session = Depends(get_db)):
    db_item = crud.get_printer(db, pid)
    if not db_item:
        raise HTTPException(404, detail="Printer not found")
    crud.delete_printer(db, db_item)

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

@router.get(
    "/{pid}/status",
    response_model=Dict[str, Any]
)
async def printer_status(
    pid: int, db: Session = Depends(get_db),
    resources: tuple[MKSPrinter, asyncio.Lock] = Depends(_get_resources),
) -> Dict[str, Any]:
    """
    Current printer snapshot in JSON.

    The structure mirrors :py:meth:`core.driver.mkswifi.MKSPrinter.poll`::

        {
          "temps":   {"T": 205.3, "Tset": 210.0, "B": 60.1, "Bset": 60.0},
          "job": "/FACTI~1.GCO"
          "progress": 37,
          "elapsed": "00:28:43",
          "state":   "PRINTING",
          "stamp":   "2025-05-06T11:32:10"
        }
    """
    mksprinter, lock = resources
    async with lock:
        try:
            printer = crud.get_printer(db, pid)
            mksprinter.host = printer.ip_address
            mksprinter.port = printer.port
            fresh = await mksprinter.poll()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    return fresh or printer.latest
