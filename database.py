from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
 
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cruk_datahub.db")

# Fix for SQLAlchemy dialect requirement
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()