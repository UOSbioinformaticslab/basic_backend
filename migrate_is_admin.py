import sqlite3
import sys

db_path = "cruk_datahub.db"

def migrate():
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Adding is_admin column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0;")
        
        # Specifically elevate the requested emails to admin
        admin_emails = [
            'woollersarah@gmail.co.uk',
            'skw24@sussex.ac.uk',
            'A.Olojede@sussex.ac.uk'
        ]

        print("Setting specific users as admins...")
        for email in admin_emails:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
            if cursor.rowcount > 0:
                print(f"  -> Elevated {email}")
            else:
                print(f"  -> User {email} not found in database (skipped)")

        conn.commit()
        print("✅ Successfully added is_admin and seeded admin users!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ The is_admin column already exists. Skipping ADD COLUMN.")
        else:
            conn.rollback()
            print(f"❌ Migration failed: {e}")
            sys.exit(1)
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
