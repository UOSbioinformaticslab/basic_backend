import sqlite3
import os
from sqlalchemy import text
from database import engine

def sync_postgres_sequences():
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                # 1. Query the Postgres catalog directly for sequences linked to 'id' columns in public schema
                query = text("""
                    SELECT 
                        t.relname AS table_name,
                        s.relname AS sequence_name
                    FROM pg_class s
                    JOIN pg_depend d ON d.objid = s.oid AND d.classid = 'pg_class'::regclass AND d.refclassid = 'pg_class'::regclass
                    JOIN pg_class t ON t.oid = d.refobjid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
                    WHERE s.relkind = 'S'
                      AND n.nspname = 'public'
                      AND a.attname = 'id';
                """)
                rows = conn.execute(query).fetchall()
                synced_tables = set()
                for table, seq in rows:
                    try:
                        conn.execute(text(f"""
                            SELECT setval(
                                'public."{seq}"',
                                COALESCE((SELECT MAX(id) FROM public."{table}"), 0) + 1,
                                false
                            );
                        """))
                        synced_tables.add(table)
                    except Exception as e:
                        print(f"Skipped sequence sync for table '{table}': {e}")

                # 2. Fallback check for any base tables in 'public' with integer 'id' columns not caught by catalog join
                fallback_query = text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                      AND table_type = 'BASE TABLE';
                """)
                all_tables = [r[0] for r in conn.execute(fallback_query).fetchall()]
                for table in all_tables:
                    if table in synced_tables:
                        continue
                    try:
                        seq_res = conn.execute(
                            text("SELECT pg_get_serial_sequence(:tbl, 'id')"),
                            {"tbl": f'public."{table}"'}
                        ).scalar()
                        if seq_res:
                            conn.execute(text(f"""
                                SELECT setval(
                                    :seq,
                                    COALESCE((SELECT MAX(id) FROM public."{table}"), 0) + 1,
                                    false
                                );
                            """), {"seq": seq_res})
                    except Exception:
                        pass # Ignore tables without sequence or without id column

            print("✅ PostgreSQL sequence synchronization complete.")
        except Exception as e:
            print(f"⚠️ PostgreSQL sequence sync warning: {e}")

def migrate():
    sync_postgres_sequences()

    db_path = os.path.join(os.path.dirname(__file__), "cruk_datahub.db")
    if not os.path.exists(db_path):
        print("Database file does not exist yet. It will be created on startup.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    user_cols = [c[1] for c in cursor.fetchall()]

    if "is_admin" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        print("Added is_admin column to users table.")

    # Ensure skw24 has admin rights
    cursor.execute('UPDATE users SET is_admin = 1 WHERE email LIKE "%skw24%" OR email LIKE "%sussex%"')

    conn.commit()
    conn.close()
    print("Database migration check complete.")

if __name__ == "__main__":
    migrate()
