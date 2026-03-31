# routers/datasets.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

# Standard Absolute Imports

from dependencies import get_current_user
import database, schemas, models, crud
router = APIRouter(prefix="/datasets", tags=["datasets"])

@router.get("/", response_model=List[schemas.DatasetResponse])
def list_all_datasets(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all datasets.
    Does NOT require a JWT token.
    """
    return db.query(models.Dataset).all()

@router.post("/", response_model=schemas.DatasetResponse)
def save_metadata_progress(
        dataset_in: schemas.DatasetBase,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # --- NEW LOGGING ---
    print("\n" + "="*40)

    print(f"📥 RECEIVED POST: DATASET")
    print(f"User: {current_user.name} (ID: {current_user.id})")

    # Check both the token context and the payload context
    payload_team_id = dataset_in.team_id
    print(f"Team ID from Frontend Payload: {payload_team_id}")
    print(f"Team ID from User Profile: {current_user.team_id}")
    print("="*40 + "\n")

    unique_ds_id = f"DS-{uuid.uuid4().hex[:8].upper()}"

    # Use the payload_team_id to ensure we don't save 'None'
    target_team_id = payload_team_id or current_user.team_id

    if not target_team_id:
        raise HTTPException(status_code=400, detail="Missing Team ID context")

    # 2. Map the React metadata_blob to the SQL model
    db_dataset = models.Dataset(
        metadata_blob=dataset_in.metadata_blob,  # The full JSON object from the form
        datasetid=unique_ds_id,  # Custom ID
        user_id=current_user.id,  # Authenticated User ID
        team_id=dataset_in.team_id,  # Authenticated Team ID
        status=models.Dataset.STATUS_DRAFT,  # Defaults to 'DRAFT'
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        # 3. Commit to the database
        db.add(db_dataset)
        db.commit()
        db.refresh(db_dataset)
        return db_dataset
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save metadata: {str(e)}"
        )


# Add this at the end of datasets.py

@router.post("/{dataset_id}/links/{project_id}", response_model=schemas.ProjectDatasetResponse)
async def link_to_project(
        dataset_id: int,
        project_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Check if the dataset exists
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 2. Check if the project exists
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 3. Check for an existing link to avoid unique constraint errors
    existing = db.query(models.ProjectDataset).filter(
        models.ProjectDataset.dataset_id == dataset_id,
        models.ProjectDataset.project_id == project_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    # 4. Create the link using the new crud function
    link_data = schemas.ProjectDatasetCreate(project_id=project_id, dataset_id=dataset_id)
    return crud.create_project_dataset_link(db, link_data)