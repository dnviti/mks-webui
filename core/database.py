from sqlalchemy import create_engine
import os
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./data/printers.db"          # ← local file, no server needed
newpath = r'./data'                 # ← path to the database file
if not os.path.exists(newpath):
    os.makedirs(newpath)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
