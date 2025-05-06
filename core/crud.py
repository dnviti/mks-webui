from sqlalchemy.orm import Session
from typing import List
from . import models, schemas

def get_printer(db: Session, printer_id: int) -> models.Printer:
    return db.query(models.Printer).get(printer_id)

def list_printers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Printer]:
    return db.query(models.Printer).offset(skip).limit(limit).all()

def create_printer(db: Session, data: schemas.PrinterCreate):
    item = models.Printer(**data.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_printer(db: Session, db_item: models.Printer, data: schemas.PrinterUpdate):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(db_item, k, v)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_printer(db: Session, db_item: models.Printer):
    db.delete(db_item)
    db.commit()
