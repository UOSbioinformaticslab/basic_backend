# schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import datetime


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
    email: EmailStr
    name: str
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