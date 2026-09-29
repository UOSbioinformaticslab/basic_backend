import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
if DATABASE_PUBLIC_URL and DATABASE_PUBLIC_URL.startswith("postgres://"):
    DATABASE_PUBLIC_URL = DATABASE_PUBLIC_URL.replace("postgres://", "postgresql://", 1)

def migrate():
    if not DATABASE_PUBLIC_URL:
        print("❌ Error: Neither DATABASE_PUBLIC_URL nor DATABASE_URL environment variable is set.")
        sys.exit(1)
    print("Connecting to remote Postgres database...")
    
    try:
        engine = create_engine(DATABASE_PUBLIC_URL)
        
        with engine.begin() as conn:
            print("Adding is_admin column to users table...")
            # Safe add column if it doesn't exist
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;"))
            
            # Specifically elevate the requested emails to admin
            admin_emails = [
                'woollersarah@gmail.co.uk',
                'skw24@sussex.ac.uk',
                'A.Olojede@sussex.ac.uk'
            ]
            
            print("Setting specific users as admins...")
            for email in admin_emails:
                result = conn.execute(
                    text("UPDATE users SET is_admin = TRUE WHERE email = :email"),
                    {"email": email}
                )
                if result.rowcount > 0:
                    print(f"  -> Elevated {email}")
                else:
                    print(f"  -> User {email} not found in database (skipped)")
                    
        print("✅ Successfully added is_admin and seeded admin users!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
