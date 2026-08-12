import sys
import os
from sqlalchemy import create_engine, text
from database import Base
import models  # to ensure all models are registered

def run():
    pg_url = "postgresql://postgres:hkJiqclpUJHSsJIhDSXiMGQFOtkDTmpX@monorail.proxy.rlwy.net:20854/railway"
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
                
                # Reset sequence for PostgreSQL if it has an id column
                if 'id' in table.columns:
                    try:
                        reset_query = f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), COALESCE((SELECT MAX(id)+1 FROM {table.name}), 1), false)"
                        conn_pg.execute(text(reset_query))
                    except Exception as e:
                        print(f"Could not reset sequence for {table.name}: {e}")
                        
            print("Successfully copied SQLite to PostgreSQL!")

if __name__ == "__main__":
    run()
