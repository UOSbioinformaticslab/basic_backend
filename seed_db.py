import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure models can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, Team, Base
from passlib.context import CryptContext

DATABASE_URL = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: Neither DATABASE_PUBLIC_URL nor DATABASE_URL environment variable is set.")
    sys.exit(1)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# I am generating the hash for the password "*abcStagingAdmin"
hashed_password = pwd_context.hash("*abcStagingAdmin")

try:
    # Ensure tables exist just in case
    Base.metadata.create_all(bind=engine)
    
    # Check if team 1 exists
    team = db.query(Team).filter(Team.id == 1).first()
    if not team:
        team = Team(id=1, name="Admin Team")
        db.add(team)
        db.commit()
        print("Created Team 1")
        
    # Check if user exists
    user = db.query(User).filter(User.email == "skw24@sussex.ac.uk").first()
    if not user:
        user = User(
            id=1,
            email="skw24@sussex.ac.uk",
            name="admin",
            hashed_password=hashed_password,
            team_id=1
        )
        db.add(user)
        db.commit()
        print("Successfully seeded admin user!")
    else:
        print("User already exists!")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
