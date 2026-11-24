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

    # Ensure is_sandbox exists on postgres teams
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE teams ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN DEFAULT FALSE;"))
                # Ensure Sandbox team exists
                res = conn.execute(text("SELECT id FROM teams WHERE name = 'Sandbox' OR is_sandbox = TRUE LIMIT 1;")).fetchone()
                if not res:
                    conn.execute(text("""
                        INSERT INTO teams (name, introduction, is_sandbox) 
                        VALUES ('Sandbox', 'Sandbox environment for test-driving data entry and validation without database persistence.', TRUE);
                    """))
                    print("✅ Created Sandbox team in PostgreSQL.")
                else:
                    conn.execute(text("UPDATE teams SET is_sandbox = TRUE WHERE id = :tid;"), {"tid": res[0]})
        except Exception as e:
            print(f"⚠️ PostgreSQL sandbox team migration warning: {e}")

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

    # Migrate teams table for is_sandbox
    cursor.execute("PRAGMA table_info(teams)")
    team_cols = [c[1] for c in cursor.fetchall()]
    if "is_sandbox" not in team_cols:
        cursor.execute("ALTER TABLE teams ADD COLUMN is_sandbox BOOLEAN DEFAULT 0")
        print("Added is_sandbox column to teams table.")

    # Ensure Sandbox team exists
    cursor.execute("SELECT id FROM teams WHERE name = 'Sandbox' OR is_sandbox = 1 LIMIT 1")
    sandbox_row = cursor.fetchone()
    if not sandbox_row:
        cursor.execute("""
            INSERT INTO teams (name, introduction, is_sandbox) 
            VALUES ('Sandbox', 'Sandbox environment for test-driving data entry and validation without database persistence.', 1)
        """)
        sandbox_id = cursor.lastrowid
        print("Created Sandbox team in SQLite.")
    else:
        sandbox_id = sandbox_row[0]
        cursor.execute("UPDATE teams SET is_sandbox = 1 WHERE id = ?", (sandbox_id,))

    # Enroll all existing users into Sandbox team if not already members
    cursor.execute("SELECT id FROM users")
    user_ids = [r[0] for r in cursor.fetchall()]
    for uid in user_ids:
        cursor.execute("SELECT user_id FROM user_teams WHERE user_id = ? AND team_id = ?", (uid, sandbox_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO user_teams (user_id, team_id, is_team_admin) VALUES (?, ?, 0)", (uid, sandbox_id))

    conn.commit()
    conn.close()
    print("Database migration check complete.")

if __name__ == "__main__":
    migrate()
