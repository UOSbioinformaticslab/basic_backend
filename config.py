# backend/fastapi-backend/config.py
import os

# In a production environment, you would use os.getenv("SECRET_KEY")
# and store the actual key in a .env file.
SECRET_KEY = "cruk-datahub-super-secret-key-123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600 # 10 hours for research sessions