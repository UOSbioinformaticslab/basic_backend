# schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


class SnomedFilterResponse(BaseModel):
    id: int
    snomed_descriptor: str
    icdo_code: str
    topography: str
    filter_code: str

    class Config:
        from_attributes = True

class CancerTermMappingCreate(BaseModel):
    topography: str
    histology: str
    associated_terms: List[dict[str, Any]]

class CancerTermMappingResponse(CancerTermMappingCreate):
    id: int

    class Config:
        from_attributes = True  # Allows Pydantic to read SQLAlchemy models

class LookupRequest(BaseModel):
    topographies: List[str]
    histologies: List[str]

# --- Dataset Schemas (Unchanged - Keeping datasetid flatcase) ---
class DatasetBase(BaseModel):
    metadata_blob: dict
    team_id: Optional[int] = None
    status: Optional[str] = "DRAFT"


class DatasetCreate(DatasetBase):
    user_id: int
    team_id: int


class DatasetResponse(DatasetBase):
    id: int
    datasetid: str
    created_at: datetime

    class Config:
        from_attributes = True

from pydantic import BaseModel
from typing import Optional, List

class DatasetSimpleResponse(BaseModel):
    id: int
    datasetid: Optional[str] = None
    name: str

    class Config:
        from_attributes = True

# --- User & Team Schemas ---
class TeamResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    team_id: int


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    team_id: int

    class Config:
        from_attributes = True


# --- Project Schemas (Updated for HDRUK/PHP Alignment) ---
class ProjectBase(BaseModel):
    # These match the $fillable array in the PHP model
    pid: Optional[str] = None
    version: Optional[str] = None
    projectGrantName: Optional[str] = None
    leadResearcher: Optional[str] = None
    leadResearchInstitute: Optional[str] = None
    grantNumbers: Optional[str] = None
    projectGrantStartDate: Optional[str] = None
    projectGrantEndDate: Optional[str] = None
    projectGrantScope: Optional[str] = None

    # Still keeping the blob for extra React-specific form data
    metadata_blob: dict
    team_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    status: str = "DRAFT"


class ProjectResponse(ProjectBase):
    id: int  # The internal database row number
    status: str
    user_id: int
    team_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Project-Dataset Link Schemas ---
class ProjectDatasetBase(BaseModel):
    project_id: int
    dataset_id: int

class ProjectDatasetCreate(ProjectDatasetBase):
    pass

class ProjectDatasetResponse(ProjectDatasetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class PublicationBase(BaseModel):
    paper_title: str
    authors: List[Dict[str, Any]]
    year_of_publication: str
    paper_doi: str
    journal_name: str
    abstract: Optional[str] = None
    url: Optional[str] = None
    team_id: str

class PublicationCreate(PublicationBase):
    pass

class Publication(PublicationBase):
    id: str

    class Config:
        from_attributes = True # Use orm_mode = True if you are on Pydantic v1

class PublicationHasDatasetBase(BaseModel):
    publication_id: str
    dataset_id: str

class PublicationHasDatasetCreate(PublicationHasDatasetBase):
    pass

class PublicationHasDataset(PublicationHasDatasetBase):
    class Config:
        from_attributes = True


def create_publication(db: Session, pub: schemas.PublicationCreate):
    # Generate a unique ID for the publication
    pub_id = str(uuid.uuid4())

    db_publication = Publication(
        id=pub_id,
        paper_title=pub.paper_title,
        authors=pub.authors,
        year_of_publication=pub.year_of_publication,
        paper_doi=pub.paper_doi,
        journal_name=pub.journal_name,
        abstract=pub.abstract,
        url=pub.url,
        team_id=pub.team_id
    )
    db.add(db_publication)
    db.commit()
    db.refresh(db_publication)
    return db_publication


def link_publication_to_dataset(db: Session, publication_id: str, dataset_id: str):
    db_link = PublicationHasDataset(
        publication_id=publication_id,
        dataset_id=dataset_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link