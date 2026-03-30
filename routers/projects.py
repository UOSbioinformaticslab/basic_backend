# routers/projects.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from dependencies import get_current_user
import database, schemas, models, crud

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=schemas.ProjectResponse)
def save_project(
    project_in: schemas.ProjectCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify a team context exists.
    # HDRUK/PHP requirements mandate that every project is linked to a team_id.
    if project_in.team_id is None:
        raise HTTPException(
            status_code=400,
            detail="No active team selected. Please select a team from the User Menu before saving."
        )

    # 2. Call the CRUD function to map the 11 fields (pid, projectGrantName, etc.)
    # and the authenticated user_id to the database.
    return crud.create_project(
        db=db,
        project=project_in,
        user_id=current_user.id,
        team_id=project_in.team_id
    )

@router.get("/", response_model=List[schemas.ProjectResponse])
def list_all_projects(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all datasets.
    Does NOT require a JWT token.
    """
    return db.query(models.Project).all()