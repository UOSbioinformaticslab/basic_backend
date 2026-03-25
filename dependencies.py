# dependencies.py
from config import SECRET_KEY, ALGORITHM # Import the same keys!
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import database, auth, models


# This matches the tokenUrl in routers/auth.py
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    # --- CRITICAL LOGGING ---
    print("\n" + "!" * 40)
    print(f"🕵️  GATEKEEPER: Validating token...")
    print(f"Token (First 15 chars): {token[:15]}...")

    try:
        # Check if the secret key matches what was used to sign it
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        print(f"✅ DECODE SUCCESS: User is {username}")

        if username is None:
            print("❌ FAIL: 'sub' field missing in token")
            raise HTTPException(status_code=401, detail="Invalid token payload")

    except JWTError as e:
        print(f"❌ DECODE FAIL: {str(e)}")  # This will tell us if it's a signature or expiry issue
        print(f"Using Secret Key: {SECRET_KEY}")
        raise HTTPException(status_code=401, detail=f"JWT Error: {str(e)}")

    user = db.query(models.User).filter(models.User.email == username).first()
    if user is None:
        print(f"❌ FAIL: User {username} not found in database")
        raise HTTPException(status_code=401, detail="User not found")

    print(f"🔓 ACCESS GRANTED: {user.name}")
    print("!" * 40 + "\n")
    return user