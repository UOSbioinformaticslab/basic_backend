import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

load_dotenv()

pg_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
if not pg_url:
    print("❌ Error: Neither DATABASE_PUBLIC_URL nor DATABASE_URL environment variable is set.")
    sys.exit(1)
if pg_url.startswith("postgres://"):
    pg_url = pg_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(pg_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    users = db.query(models.User).all()
    print("Users found:", len(users))
    for u in users:
        print("User:", u.id, u.email, u.name)
        print("Teams:", [t.id for t in u.teams])
except Exception as e:
    import traceback
    traceback.print_exc()
