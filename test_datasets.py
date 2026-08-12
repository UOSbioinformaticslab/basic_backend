import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
import schemas
from pydantic import TypeAdapter
from typing import List

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
        "team_name": db_dataset.team.name if db_dataset.team else None,
        "status": db_dataset.status,
        "active": bool(db_dataset.active),
        "has_draft": db_dataset.draft_metadata_blob is not None,
        "created_at": db_dataset.created_at
    }

sqlite_url = "sqlite:///cruk_datahub.db"
engine = create_engine(sqlite_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    active_datasets = db.query(models.Dataset).filter(models.Dataset.active == True).all()
    print("Found active datasets:", len(active_datasets))
    
    # Try to build response dicts
    res_dicts = [build_dataset_response(ds) for ds in active_datasets]
    
    # Try to validate through Pydantic
    adapter = TypeAdapter(List[schemas.DatasetResponse])
    adapter.validate_python(res_dicts)
    
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
