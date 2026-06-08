from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import models
from database import get_db
import schemas

router = APIRouter(
    prefix="/snomed-filters",
    tags=["snomed-filters"]
)


@router.get("", response_model=List[schemas.SnomedFilterResponse])
def get_snomed_filters(db: Session = Depends(get_db)):
    filters = db.query(models.SnomedFilter).all()
    return filters

@router.get("/{snomed_id}", response_model=schemas.SnomedFilterResponse)
def get_single_snomed_filter(snomed_id: int, db: Session = Depends(get_db)):
    filter_record = db.query(models.SnomedFilter).filter(models.SnomedFilter.id == snomed_id).first()
    if not filter_record:
        raise HTTPException(status_code=404, detail="SNOMED code not found")
    return filter_record