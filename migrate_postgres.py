import sys
from sqlalchemy import create_engine, text

DATABASE_PUBLIC_URL = "postgresql://postgres:VwveDOCnQiRDIbKecOkrUCbxWQviyYFQ@mainline.proxy.rlwy.net:31273/railway"

def migrate():
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
