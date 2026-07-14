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
    return [{"email": u.email, "name": u.name, "teams": [t.id for t in u.teams]} for u in users]

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