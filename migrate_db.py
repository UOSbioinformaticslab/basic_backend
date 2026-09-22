import sqlite3
import os
from sqlalchemy import text
from database import engine

def sync_postgres_sequences():
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                query = text("""
                    SELECT table_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND column_name = 'id';
                """)
                result = conn.execute(query)
                tables = [row[0] for row in result.fetchall()]
                for table in tables:
                    try:
                        seq_sql = text(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table}', 'id'),
                                COALESCE((SELECT MAX(id) FROM "{table}"), 0) + 1,
                                false
                            );
                        """)
                        conn.execute(seq_sql)
                    except Exception as e:
                        print(f"Skipped sequence sync for table '{table}': {e}")
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
