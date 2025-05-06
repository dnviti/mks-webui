from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PrinterBase(BaseModel):
    name: str = Field(..., max_length=64)
    ip_address: str
    port: int = 80

class PrinterCreate(PrinterBase):
    pass

class PrinterUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None

class PrinterOut(PrinterBase):
    id: int

    # ⬇️  NEW v2-style config
    model_config = ConfigDict(from_attributes=True)
    # (You could also write a nested class:
    #    class Config: from_attributes = True
    #  but `model_config` is the canonical v2 style)
