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

def build_dataset_response(db_dataset: models.Dataset, use_draft: bool = False) -> dict:
    blob = db_dataset.draft_metadata_blob if (use_draft and db_dataset.draft_metadata_blob is not None) else db_dataset.metadata_blob
    if blob is None and db_dataset.draft_metadata_blob is not None:
        blob = db_dataset.draft_metadata_blob
    return {
        "id": db_dataset.id,
        "datasetid": db_dataset.datasetid,
        "metadata_blob": blob or {},
        "draft_metadata_blob": db_dataset.draft_metadata_blob,
        "team_id": db_dataset.team_id,
        "status": db_dataset.status,
        "active": bool(db_dataset.active),
        "has_draft": db_dataset.draft_metadata_blob is not None,
        "created_at": db_dataset.created_at
    }


@router.get("/", response_model=List[schemas.DatasetResponse])
def list_all_datasets(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all ACTIVE datasets.
    Does NOT require a JWT token.
    """
    active_datasets = db.query(models.Dataset).filter(models.Dataset.active == True).all()
    return [build_dataset_response(ds) for ds in active_datasets]


@router.get("/search", response_model=List[schemas.DatasetResponse])
def search_datasets(
        title: str,
        db: Session = Depends(database.get_db)
):
    """
    Search for active datasets by checking the specific summary.title path.
    """
    search_term = f"%{title}%"

    datasets = db.query(models.Dataset).filter(
        models.Dataset.active == True,
        func.json_extract(models.Dataset.metadata_blob, '$.summary.title').ilike(search_term)
    ).all()

    return [build_dataset_response(ds) for ds in datasets]


@router.get("/list/simple", response_model=List[schemas.DatasetSimpleResponse])
def get_simple_dataset_list(db: Session = Depends(database.get_db)):
    # Query all dataset records so editors can see drafts and active records
    records = db.query(
        models.Dataset.id,
        models.Dataset.datasetid,
        models.Dataset.metadata_blob,
        models.Dataset.draft_metadata_blob,
        models.Dataset.active
    ).all()

    results = []
    for record in records:
        # Prefer draft title if present, otherwise active title
        blob = record.draft_metadata_blob if record.draft_metadata_blob is not None else record.metadata_blob
        title = f"Dataset {record.id}"
        if isinstance(blob, dict):
            title = blob.get("summary", {}).get("title", title)

        results.append({
            "id": record.id,
            "datasetid": record.datasetid,
            "computed_title": title,
            "active": bool(record.active),
            "has_draft": record.draft_metadata_blob is not None
        })
    return results


@router.get("/{dataset_id}", response_model=schemas.DatasetResponse)
def get_public_dataset(
        dataset_id: int,
        preview: bool = False,
        db: Session = Depends(database.get_db)
):
    # Look up the dataset by its primary key ID
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # If dataset is not active and not in preview mode, hide it from public view
    if not db_dataset.active and not preview:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return build_dataset_response(db_dataset, use_draft=preview)


@router.post("/", response_model=schemas.DatasetResponse)
def save_metadata_progress(
        dataset_in: schemas.DatasetBase,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    payload_team_id = dataset_in.team_id
    unique_ds_id = f"DS-{uuid.uuid4().hex[:8].upper()}"
    target_team_id = payload_team_id

    if not target_team_id:
        raise HTTPException(status_code=400, detail="Missing Team ID context")

    user_team_ids = [team.id for team in current_user.teams]
    if target_team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the specified team")

    is_active = bool(dataset_in.active or dataset_in.status == models.Dataset.STATUS_ACTIVE)

    db_dataset = models.Dataset(
        metadata_blob=dataset_in.metadata_blob if is_active else {},
        draft_metadata_blob=None if is_active else dataset_in.metadata_blob,
        datasetid=unique_ds_id,
        user_id=current_user.id,
        team_id=dataset_in.team_id,
        active=is_active,
        status=models.Dataset.STATUS_ACTIVE if is_active else models.Dataset.STATUS_DRAFT,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        db.add(db_dataset)
        db.commit()
        db.refresh(db_dataset)
        return build_dataset_response(db_dataset, use_draft=not is_active)
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
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if dataset_in.team_id:
        user_team_ids = [team.id for team in current_user.teams]
        if dataset_in.team_id not in user_team_ids:
            raise HTTPException(status_code=403, detail="User is not a member of the specified team")
        db_dataset.team_id = dataset_in.team_id

    # Check for unpublish request
    if dataset_in.unpublish:
        db_dataset.active = False
        db_dataset.status = models.Dataset.STATUS_DRAFT
    elif dataset_in.active or dataset_in.status == models.Dataset.STATUS_ACTIVE:
        # Publish/Make Active: promote draft data (or payload) to live metadata_blob
        incoming_blob = dataset_in.metadata_blob or db_dataset.draft_metadata_blob or db_dataset.metadata_blob
        db_dataset.metadata_blob = incoming_blob
        db_dataset.draft_metadata_blob = None
        db_dataset.active = True
        db_dataset.status = models.Dataset.STATUS_ACTIVE
    else:
        # Save as Draft
        if db_dataset.active:
            # Record is already published: save new edits as working draft
            db_dataset.draft_metadata_blob = dataset_in.metadata_blob
        else:
            # Record is currently draft only
            db_dataset.metadata_blob = dataset_in.metadata_blob
            db_dataset.draft_metadata_blob = None
            db_dataset.active = False
            db_dataset.status = models.Dataset.STATUS_DRAFT

    try:
        db.commit()
        db.refresh(db_dataset)
        return build_dataset_response(db_dataset, use_draft=not db_dataset.active)
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

