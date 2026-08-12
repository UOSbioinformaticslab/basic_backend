import sqlite3
import sys

db_path = "cruk_datahub.db"

def migrate():
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Disabling foreign keys...")
        cursor.execute("PRAGMA foreign_keys=OFF;")
        cursor.execute("BEGIN TRANSACTION;")

        print("Creating users_new table without team_id...")
        cursor.execute("""
            CREATE TABLE users_new (
                id INTEGER NOT NULL, 
                email VARCHAR, 
                name VARCHAR, 
                hashed_password VARCHAR, 
                PRIMARY KEY (id)
            );
        """)

        print("Copying data from users to users_new...")
        cursor.execute("""
            INSERT INTO users_new (id, email, name, hashed_password)
            SELECT id, email, name, hashed_password FROM users;
        """)

        print("Dropping legacy users table...")
        cursor.execute("DROP TABLE users;")

        print("Renaming users_new to users...")
        cursor.execute("ALTER TABLE users_new RENAME TO users;")

        print("Recreating indexes...")
        cursor.execute("CREATE INDEX ix_users_id ON users (id);")
        cursor.execute("CREATE UNIQUE INDEX ix_users_email ON users (email);")

        cursor.execute("COMMIT;")
        print("✅ Successfully migrated local SQLite database! legacy team_id column removed.")
    except Exception as e:
        cursor.execute("ROLLBACK;")
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        print("Re-enabling foreign keys...")
        cursor.execute("PRAGMA foreign_keys=ON;")
        conn.close()

if __name__ == "__main__":
    migrate()
