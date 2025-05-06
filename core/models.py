from sqlalchemy import Column, Integer, String
from .database import Base

class Printer(Base):
    __tablename__ = "printers"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(64),  nullable=False)
    ip_address  = Column(String(64),  nullable=False)
    port        = Column(Integer,       default=80)

    def __repr__(self) -> str:
        return f"<Printer {self.name} ({self.ip_address}:{self.port})>"
