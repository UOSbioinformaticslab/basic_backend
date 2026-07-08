# schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
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

class DatasetSimpleResponse(BaseModel):
    id: int
    datasetid: Optional[str] = None
    computed_title: str #this is drawn from the @property in models.py

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
    project_grant_name: Optional[str] = None
    lead_researcher: Optional[str] = None
    lead_research_institute: Optional[str] = None
    grant_numbers: Optional[str] = None
    project_grant_start_date: Optional[str] = None
    project_grant_end_date: Optional[str] = None
    project_grant_scope: Optional[str] = None

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
    authors: List[str] = []
    year_of_publication: str
    paper_doi: str
    journal_name: str
    abstract: Optional[str] = None
    url: Optional[str] = None
    team_id: int

class PublicationCreate(PublicationBase):
    pass

class Publication(PublicationBase):
    id: int
    datasets: List[DatasetSimpleResponse] = []  # MUST be present
    projects: List[ProjectResponse] = []  # MUST be present

    class Config:
        from_attributes = True # Use orm_mode = True if you are on Pydantic v1

class PublicationHasDatasetBase(BaseModel):
    publication_id: int
    dataset_id: int

class PublicationHasDatasetCreate(PublicationHasDatasetBase):
    pass

class PublicationHasDataset(PublicationHasDatasetBase):
    class Config:
        from_attributes = True

class PublicationHasProjectBase(BaseModel):
    publication_id: int
    project_id: int

class PublicationHasProjectCreate(PublicationHasProjectBase):
    pass

class PublicationHasProject(PublicationHasProjectBase):
    class Config:
        from_attributes = True

class DOICreateRequest(BaseModel):
    doi: str
    team_id: int