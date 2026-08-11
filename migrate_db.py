import sqlite3
import os

def migrate():
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
