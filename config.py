import os
from dotenv import load_dotenv

# This loads the variables from .env into the os environment
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()

# Now you safely retrieve them without hardcoding anything
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM")
val = os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "600")
ACCESS_TOKEN_EXPIRE_MINUTES = int(val.split('#')[0].strip()) if val else 600
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL")
DATABASE_URL = os.environ.get("DATABASE_URL") or DATABASE_PUBLIC_URL
if not DATABASE_URL or DATABASE_URL == "sqlite:///./cruk_datahub.db":
    db_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "cruk_datahub.db"))
    DATABASE_URL = f"sqlite:///{db_file}"

# SQLAlchemy 1.4+ removed support for "postgres://", requires "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

