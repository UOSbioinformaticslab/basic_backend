# models.py
from sqlalchemy import Table, Column, Integer, String, JSON, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# Association table for Many-to-Many
user_teams = Table(
    "user_teams",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("team_id", Integer, ForeignKey("teams.id"), primary_key=True),
)


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    datasets = relationship("Dataset", back_populates="team")
    members = relationship("User", secondary=user_teams, back_populates="teams")
    projects = relationship("Project", back_populates="team")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)  # For secure storage
    team_id = Column(Integer, ForeignKey("teams.id"))

    # Relationships to easily access team, dataset, and project data
    teams = relationship("Team", secondary=user_teams, back_populates="members")
    datasets = relationship("Dataset", back_populates="user")
    projects = relationship("Project", back_populates="user")


class Dataset(Base):
    __tablename__ = "datasets"

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_DRAFT = 'DRAFT'
    STATUS_ARCHIVED = 'ARCHIVED'

    id = Column(Integer, primary_key=True, index=True)
    datasetid = Column(String, unique=True)  # e.g. CRUK_001
    metadata_blob = Column(JSON)  # The actual React form data
    status = Column(String, default="DRAFT")
    user_id = Column(Integer, ForeignKey("users.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="datasets")
    team = relationship("Team", back_populates="datasets")


class Project(Base):
    __tablename__ = "projects"

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_DRAFT = 'DRAFT'
    STATUS_ARCHIVED = 'ARCHIVED'

    id = Column(Integer, primary_key=True, index=True)

    # Specific columns to match the HDRUK/PHP $fillable structure
    pid = Column(String, unique=True, index=True)
    version = Column(String)
    projectGrantName = Column(String)
    leadResearcher = Column(String)
    leadResearchInstitute = Column(String)
    grantNumbers = Column(String)
    projectGrantStartDate = Column(String)  # Stored as string for frontend flexibility
    projectGrantEndDate = Column(String)
    projectGrantScope = Column(String)

    # Metadata blob for catch-all React form storage
    metadata_blob = Column(JSON)
    status = Column(String, default="DRAFT")

    user_id = Column(Integer, ForeignKey("users.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))

    # Timestamps for record lifecycle management
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    team = relationship("Team", back_populates="projects")