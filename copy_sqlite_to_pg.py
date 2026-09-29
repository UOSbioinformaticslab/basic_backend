import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from database import Base
import models  # to ensure all models are registered

load_dotenv()

def run():
    pg_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not pg_url:
        print("❌ Error: Neither DATABASE_PUBLIC_URL nor DATABASE_URL environment variable is set.")
        sys.exit(1)
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    sqlite_url = "sqlite:///cruk_datahub.db"

    pg_engine = create_engine(pg_url)
    sqlite_engine = create_engine(sqlite_url)

    print("Recreating tables in PostgreSQL...")
    Base.metadata.drop_all(pg_engine)
    Base.metadata.create_all(pg_engine)

    with sqlite_engine.connect() as conn_lite:
        with pg_engine.begin() as conn_pg:
            print("Copying data from SQLite to PostgreSQL...")
            for table in Base.metadata.sorted_tables:
                print(f"Copying {table.name}...")
                rows = conn_lite.execute(text(f"SELECT * FROM {table.name}")).fetchall()
                if rows:
                    dicts = [dict(row._mapping) for row in rows]
                    
                    # Convert SQLite datetime strings to datetime objects for Postgres if needed
                    from datetime import datetime
                    for d in dicts:
                        for k, v in d.items():
                            if isinstance(v, str):
                                try:
                                    d[k] = datetime.fromisoformat(v)
                                except ValueError:
                                    pass
                                    
                    conn_pg.execute(table.insert(), dicts)
                
                # Reset sequence for PostgreSQL if it has an integer id column
                if 'id' in table.columns and hasattr(table.columns['id'].type, 'python_type') and table.columns['id'].type.python_type is int:
                    try:
                        reset_query = f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                        conn_pg.execute(text(reset_query))
                    except Exception as e:
                        print(f"Could not reset sequence for {table.name}: {e}")
                        
            print("Successfully copied SQLite to PostgreSQL!")

if __name__ == "__main__":
    run()
