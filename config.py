import os
from dotenv import load_dotenv

# This loads the variables from .env into the os environment
load_dotenv()

# Now you safely retrieve them without hardcoding anything
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL")
DATABASE_URL = os.environ.get("DATABASE_URL") or DATABASE_PUBLIC_URL

# SQLAlchemy 1.4+ removed support for "postgres://", requires "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

