# crud.py
from sqlalchemy.orm import Session
import models, schemas
import uuid


def update_dataset(db: Session, dataset: schemas.DatasetCreate, user_id: int, team_id: int):
    # Maintains 'datasetid' naming to match your frontend requirement
    db_dataset = models.Dataset(
        **dataset.model_dump(),
        datasetid=f"DS-{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id,
        team_id=team_id
    )
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def create_project(db: Session, project: schemas.ProjectCreate, user_id: int, team_id: int):
    # Convert schema to dict to allow PID injection if missing
    project_data = project.model_dump()

    # Logic to generate a unique pid (Persistent ID)
    # If the grant stub didn't provide a PID, we generate a CRUK-specific one
    if not project_data.get("pid"):
        project_data["pid"] = f"PRJ-{uuid.uuid4().hex[:8].upper()}"

    # **project_data now automatically populates the 11 explicit columns
    # (projectGrantName, leadResearcher, etc.) defined in models.py
    db_project = models.Project(
        **project_data,
        user_id=user_id,

    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project