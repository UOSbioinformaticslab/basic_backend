# schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime



class DatasetBase(BaseModel):
    metadata_blob: dict  # Validates the JSON object
    status: Optional[str] = "DRAFT"


class DatasetCreate(DatasetBase):
    user_id: int
    team_id: int

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


class DatasetResponse(DatasetBase):
    id: int
    datasetid: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    metadata_blob: dict

class ProjectCreate(ProjectBase):
    status: str = "DRAFT"

class ProjectResponse(ProjectBase):
    id: int
    project_id: str
    status: str
    user_id: int
    team_id: int

    class Config:
        from_attributes = True