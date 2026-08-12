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

    print("Recreating tables in SQLite...")
    Base.metadata.drop_all(sqlite_engine)
    Base.metadata.create_all(sqlite_engine)

    with pg_engine.connect() as conn_pg:
        with sqlite_engine.begin() as conn_lite:
            print("Copying data from PostgreSQL back to SQLite...")
            for table in Base.metadata.sorted_tables:
                print(f"Copying {table.name}...")
                rows = conn_pg.execute(text(f"SELECT * FROM {table.name}")).fetchall()
                if rows:
                    dicts = [dict(row._mapping) for row in rows]
                    
                    # Ensure datetime strings from PG are properly handled if needed, though SQLAlchemy PG dialect might return datetime objects directly!
                    # Let's double check if we need conversion
                    from datetime import datetime
                    for d in dicts:
                        for k, v in d.items():
                            if isinstance(v, str):
                                try:
                                    d[k] = datetime.fromisoformat(v)
                                except ValueError:
                                    pass
                                    
                    conn_lite.execute(table.insert(), dicts)
                        
            print("Successfully restored SQLite from PostgreSQL!")

if __name__ == "__main__":
    run()
