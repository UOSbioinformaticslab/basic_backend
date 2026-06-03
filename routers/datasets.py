# routers/datasets.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import String, func
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


@router.get("/{dataset_id}", response_model=schemas.DatasetResponse)
def get_public_dataset(dataset_id: int, db: Session = Depends(database.get_db)):
    # Look up the dataset by its primary key ID
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return db_dataset

@router.get("/search", response_model=List[schemas.DatasetResponse])
def search_datasets(
        title: str,
        db: Session = Depends(database.get_db)
):
    """
    Search for a dataset by checking the specific summary.title path.
    """
    search_term = f"%{title}%"

    # Extracts the specific key before applying the ILIKE filter
    datasets = db.query(models.Dataset).filter(
        func.json_extract(models.Dataset.metadata_blob, '$.summary.title').ilike(search_term)
    ).all()

    return datasets


@router.get("/list/simple", response_model=List[schemas.DatasetSimpleResponse])
def get_simple_dataset_list(db: Session = Depends(database.get_db)):
    """
    Returns a lightweight list of all datasets containing only their ID,
    datasetid, and extracted name.
    """
    records = db.query(
        models.Dataset.id,
        models.Dataset.datasetid,
        models.Dataset.metadata_blob
    ).all()

    results = []
    for record in records:
        name = "Untitled Dataset"

        # Safely extract the title from the JSON blob if it exists
        if record.metadata_blob and isinstance(record.metadata_blob, dict):
            name = record.metadata_blob.get("summary", {}).get("title", name)

        results.append({
            "id": record.id,
            "datasetid": record.datasetid,
            "name": name
        })

    return results

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


@router.put("/{dataset_id}", response_model=schemas.DatasetResponse)
def update_metadata_progress(
        dataset_id: int,
        dataset_in: schemas.DatasetBase,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Retrieve the existing dataset from the database
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 2. Update the fields with the incoming data
    db_dataset.metadata_blob = dataset_in.metadata_blob
    db_dataset.team_id = dataset_in.team_id

    # If your model/schema tracks status (like "DRAFT"), update it as well
    if hasattr(dataset_in, 'status') and dataset_in.status:
        db_dataset.status = dataset_in.status

    # 3. Commit the changes
    try:
        db.commit()
        db.refresh(db_dataset)
        return db_dataset
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update metadata: {str(e)}"
        )

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


@router.delete("/{dataset_id}")
def delete_dataset(
        dataset_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        db.delete(db_dataset)
        db.commit()
        return {"message": "Dataset successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete dataset: {str(e)}"
        )


@router.get("/extra-terms/{mapping_id}", response_model=schemas.CancerTermMappingResponse)
def get_extra_term_by_id(
        mapping_id: int,
        db: Session = Depends(database.get_db)
):
    """
    Retrieve a specific cancer term mapping record by its primary key ID.
    """
    record = db.query(models.CancerTermMapping).filter(
        models.CancerTermMapping.id == mapping_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Mapping record not found")

    return record


@router.post("/extra-terms/record", response_model=schemas.CancerTermMappingResponse)
def post_new_extra_term(
        payload: schemas.CancerTermMappingCreate,
        db: Session = Depends(database.get_db)
):
    """
    Insert a new cancer term mapping record into the standalone database table.
    """
    db_record = models.CancerTermMapping(
        topography=payload.topography,
        histology=payload.histology,
        associated_terms=payload.associated_terms
    )

    try:
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        return db_record
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database insertion failed: {str(e)}"
        )

@router.post("/extra-terms")
def get_matching_terms(
        req: schemas.LookupRequest,
        db: Session = Depends(database.get_db)
):
    """
    Given a list of topography and histology labels, returns a nested
    mapping dictionary containing matching supplementary ontology records.
    """
    # Filter for mapping entries matching the criteria fields
    records = db.query(models.CancerTermMapping).filter(
        models.CancerTermMapping.topography.in_(req.topographies),
        models.CancerTermMapping.histology.in_(req.histologies)
    ).all()

    # Rebuild the records back into the nested mapping layout
    nested_map = {}
    for record in records:
        if record.topography not in nested_map:
            nested_map[record.topography] = {}
        nested_map[record.topography][record.histology] = record.associated_terms

    return nested_map