import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
if DATABASE_PUBLIC_URL and DATABASE_PUBLIC_URL.startswith("postgres://"):
    DATABASE_PUBLIC_URL = DATABASE_PUBLIC_URL.replace("postgres://", "postgresql://", 1)

def migrate():
    if not DATABASE_PUBLIC_URL:
        print("❌ Error: Neither DATABASE_PUBLIC_URL nor DATABASE_URL environment variable is set.")
        sys.exit(1)
    print(f"Connecting to remote Postgres database...")
    
    # We must ensure psycopg2 or similar is installed.
    # FastAPI backends typically have it if they use Postgres.
    try:
        engine = create_engine(DATABASE_PUBLIC_URL)
        with engine.begin() as conn:
            print("Executing ALTER TABLE users DROP COLUMN team_id CASCADE...")
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS team_id CASCADE;"))
            
        print("✅ Successfully dropped legacy team_id column from the remote database!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
