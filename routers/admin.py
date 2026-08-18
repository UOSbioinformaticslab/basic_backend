from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Absolute imports from the backend root
import models
import schemas
import database
import auth  # Used for password hashing

router = APIRouter(prefix="/admin", tags=["admin"])


# --- TEAM MANAGEMENT ---

@router.post("/teams", response_model=schemas.TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(name: str, db: Session = Depends(database.get_db)):
    """
    Creates a new research team. 
    In the PHP model, this maps to the team_id.
    """
    existing_team = db.query(models.Team).filter(models.Team.name == name).first()
    if existing_team:
        raise HTTPException(status_code=400, detail="Team name already exists")

    db_team = models.Team(name=name)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team


@router.get("/teams", response_model=List[schemas.TeamResponse])
def list_teams(db: Session = Depends(database.get_db)):
    return db.query(models.Team).all()


# --- USER MANAGEMENT ---

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """
    Creates a user and optionally appends an initial team
    to the many-to-many relationship list.
    """
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = auth.get_password_hash(user_in.password)
    db_user = models.User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=hashed_pwd
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users")
def list_users(db: Session = Depends(database.get_db)):
    users = db.query(models.User).all()
    # Manual conversion to see what's actually coming back
    return [{"id": u.id, "email": u.email, "name": u.name, "is_admin": u.is_admin, "teams": [t.id for t in u.teams]} for u in users]

@router.post("/users/{user_id}/teams/{team_id}", response_model=schemas.UserResponse)
def add_user_to_team(user_id: int, team_id: int, db: Session = Depends(database.get_db)):
    """
    Associates an existing user with an additional team.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if team in user.teams:
        raise HTTPException(status_code=400, detail="User is already in this team")

    user.teams.append(team)
    db.commit()
    db.refresh(user)

    return user

from pydantic import BaseModel

class AdminUpdate(BaseModel):
    is_admin: bool

class PasswordUpdate(BaseModel):
    new_password: str

@router.put("/users/{user_id}/admin")
def toggle_admin(user_id: int, payload: AdminUpdate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = payload.is_admin
    db.commit()
    return {"message": "Admin status updated"}

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

@router.put("/users/{user_id}/password")
def change_password(user_id: int, payload: PasswordUpdate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = auth.get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed"}

@router.delete("/teams/{team_id}")
def delete_team(team_id: int, delete_projects: bool = False, db: Session = Depends(database.get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if delete_projects:
        # Assuming cascading deletes or manual deletes here if needed
        pass
    db.delete(team)
    db.commit()
    return {"message": "Team deleted"}

@router.delete("/users/{user_id}/teams/{team_id}")
def remove_user_from_team(user_id: int, team_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if team in user.teams:
        user.teams.remove(team)
        db.commit()
    return {"message": "User removed from team"}

@router.get("/invitations", response_model=List[schemas.TeamInvitationResponse])
def get_all_invitations(db: Session = Depends(database.get_db)):
    return db.query(models.TeamInvitation).all()

@router.get("/user_team_links")
def get_user_team_links(db: Session = Depends(database.get_db)):
    # Query the association table directly
    links = db.query(models.user_teams).all()
    return [{"user_id": link.user_id, "team_id": link.team_id, "is_team_admin": link.is_team_admin} for link in links]

@router.put("/users/{user_id}/teams/{team_id}/admin")
def toggle_team_admin(user_id: int, team_id: int, payload: AdminUpdate, db: Session = Depends(database.get_db)):
    # Update the association table directly
    stmt = (
        models.user_teams.update()
        .where(
            (models.user_teams.c.user_id == user_id) & 
            (models.user_teams.c.team_id == team_id)
        )
        .values(is_team_admin=payload.is_admin)
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User-Team link not found")
    db.commit()
    return {"message": "Team Admin status updated"}
