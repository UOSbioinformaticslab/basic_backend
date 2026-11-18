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
        raise HTTPException(status_code=401, detail=f"JWT Error: {str(e)}")

    user = db.query(models.User).filter(models.User.email == username).first()
    if user is None:
        print(f"❌ FAIL: User {username} not found in database")
        raise HTTPException(status_code=401, detail="User not found")

    print(f"🔓 ACCESS GRANTED: {user.name}")
    print("!" * 40 + "\n")
    return user


async def get_current_admin_user(current_user: models.User = Depends(get_current_user)):
    """Requires the authenticated user to be a global admin."""
    if not bool(getattr(current_user, "is_admin", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def verify_team_member(team_id: int, current_user: models.User):
    """Ensures the user is a member of the specified team or a global admin."""
    if bool(getattr(current_user, "is_admin", False)):
        return
    if not any(t.id == team_id for t in current_user.teams):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team membership required",
        )


def verify_team_admin(team_id: int, current_user: models.User, db: Session):
    """Ensures the user is a team admin for the specified team or a global admin."""
    if bool(getattr(current_user, "is_admin", False)):
        return
    link = (
        db.query(models.user_teams)
        .filter_by(user_id=current_user.id, team_id=team_id)
        .first()
    )
    if not link or not bool(link.is_team_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team admin privileges required",
        )