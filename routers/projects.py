# routers/projects.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session, selectinload
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

    user_team_ids = [team.id for team in current_user.teams]
    if project_in.team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the specified team")

    # 2. Call the CRUD function to map the 11 fields (pid, project_grant_name, etc.)
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
    if project_in.team_id:
        user_team_ids = [team.id for team in current_user.teams]
        if project_in.team_id not in user_team_ids:
            raise HTTPException(status_code=403, detail="User is not a member of the specified team")

    # exclude_unset=True ensures we only update fields that were actually sent in the payload
    update_data = project_in.dict(exclude_unset=True) if hasattr(project_in, 'dict') else project_in.model_dump(exclude_unset=True)
    dataset_ids = update_data.pop("dataset_ids", None)
    if current_user and current_user.id:
        update_data["user_id"] = current_user.id

    for key, value in update_data.items():
        setattr(db_project, key, value)

    # 3. Commit the changes
    try:
        if dataset_ids is not None:
            db.query(models.ProjectDataset).filter(models.ProjectDataset.project_id == db_project.id).delete()
            for did in dataset_ids:
                db.add(models.ProjectDataset(project_id=db_project.id, dataset_id=did))

        db.commit()
        db_project = db.query(models.Project).options(
            selectinload(models.Project.datasets),
            selectinload(models.Project.publications),
            selectinload(models.Project.tools)
        ).filter(models.Project.id == db_project.id).first()
        return db_project
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project: {str(e)}"
        )


@router.get("/team/{team_id}")
def get_team_projects(
    team_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_admin and team_id not in [t.id for t in current_user.teams]:
        raise HTTPException(status_code=403, detail="Not a member of this team")

    projects = db.query(models.Project).filter(models.Project.team_id == team_id).all()
    result = []
    for p in projects:
        name = p.project_grant_name
        if not name and isinstance(p.metadata_blob, dict):
            name = p.metadata_blob.get("summary", {}).get("title") or p.metadata_blob.get("project_grant_name")
        title = name or p.pid or f"Project {p.id}"
        result.append({
            "id": p.id,
            "pid": p.pid,
            "title": title,
            "project_grant_name": title,
            "status": p.status
        })

    result.sort(key=lambda x: (x["title"] or "").lower())
    return result


@router.get("/", response_model=List[schemas.ProjectResponse])
def list_all_projects(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all projects.
    Does NOT require a JWT token.
    """
    return db.query(models.Project).options(
        selectinload(models.Project.datasets),
        selectinload(models.Project.publications),
        selectinload(models.Project.tools)
    ).all()


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


@router.get("/{project_pid:path}", response_model=schemas.ProjectResponse)
def get_project(project_pid: str, db: Session = Depends(database.get_db)):
    """
    Retrieve a specific project by its PID (which may contain slashes) or internal ID.
    """
    query = db.query(models.Project).options(
        selectinload(models.Project.datasets),
        selectinload(models.Project.publications),
        selectinload(models.Project.tools)
    )

    db_project = query.filter(models.Project.pid == project_pid).first()

    if not db_project and project_pid.isdigit():
        db_project = query.filter(models.Project.id == int(project_pid)).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    return db_project


@router.post("/{project_id}/links/{dataset_id}", response_model=schemas.ProjectDatasetResponse)
async def link_project_to_dataset(
        project_id: int,
        dataset_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Check if the project exists
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Check if the dataset exists
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 3. Check for an existing link
    existing = db.query(models.ProjectDataset).filter(
        models.ProjectDataset.project_id == project_id,
        models.ProjectDataset.dataset_id == dataset_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    # 4. Create the link
    link_data = schemas.ProjectDatasetCreate(project_id=project_id, dataset_id=dataset_id)
    return crud.create_project_dataset_link(db, link_data)


@router.delete("/{project_id}/links/{dataset_id}")
async def unlink_project_from_dataset(
        project_id: int,
        dataset_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    link = db.query(models.ProjectDataset).filter(
        models.ProjectDataset.project_id == project_id,
        models.ProjectDataset.dataset_id == dataset_id
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Link between project and dataset not found")

    try:
        db.delete(link)
        db.commit()
        return {"message": "Link successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete link: {str(e)}")