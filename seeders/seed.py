# seed.py
import os
import sys
# Maintain the path adjustment for the seeders directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

import models
from auth import get_password_hash
from config import SWOOLLER_PASSWORD
from database import SessionLocal, engine, Base

def seed_data():
    db = SessionLocal()

