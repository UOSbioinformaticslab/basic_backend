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


@router.put("/{project_id}", response_model=schemas.ProjectResponse)
def update_project(
        project_id: int,
        project_in: schemas.ProjectCreate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Retrieve the existing project from the database
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Update the fields dynamically
    # exclude_unset=True ensures we only update fields that were actually sent in the payload
    update_data = project_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)

    # 3. Commit the changes
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project: {str(e)}"
        )

@router.get("/", response_model=List[schemas.ProjectResponse])
def list_all_projects(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all datasets.
    Does NOT require a JWT token.
    """
    return db.query(models.Project).all()


@router.delete("/{project_id}")
def delete_project(
        project_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        db.delete(db_project)
        db.commit()
        return {"message": "Project successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )