import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

pg_url = "postgresql://postgres:hkJiqclpUJHSsJIhDSXiMGQFOtkDTmpX@monorail.proxy.rlwy.net:20854/railway"
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
