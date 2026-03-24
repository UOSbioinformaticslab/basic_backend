# crud.py
from sqlalchemy.orm import Session
import models, schemas
import uuid

def update_dataset(db: Session, dataset: schemas.DatasetCreate, user_id: int, team_id: int):
    db_dataset = models.Dataset(
        **dataset.model_dump(),
        datasetid=f"DS-{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id, # Added
        team_id=team_id   # Added
    )
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset

def create_project(db: Session, project: schemas.ProjectCreate, user_id: int, team_id: int):
    # Logic to generate a unique project_id (e.g., PRJ-XXXX)
    db_project = models.Project(
        **project.model_dump(),
        project_id=f"PRJ-{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id,
        team_id=team_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project