# crud.py
from sqlalchemy.orm import Session, selectinload
import models, schemas
import uuid


def update_dataset(db: Session, dataset: schemas.DatasetCreate, user_id: int, team_id: int):
    # Maintains 'datasetid' naming to match your frontend requirement
    db_dataset = models.Dataset(
        **dataset.model_dump(),
        datasetid=f"DS-{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id,
        team_id=team_id
    )
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


def create_project(db: Session, project: schemas.ProjectCreate, user_id: int, team_id: int):
    # Convert schema to dict to allow PID injection if missing
    project_data = project.model_dump()

    # Logic to generate a unique pid (Persistent ID)
    # If the grant stub didn't provide a PID, we generate a CRUK-specific one
    if not project_data.get("pid"):
        project_data["pid"] = f"PRJ-{uuid.uuid4().hex[:8].upper()}"

    # **project_data now automatically populates the 11 explicit columns
    # (projectGrantName, leadResearcher, etc.) defined in models.py
    db_project = models.Project(
        **project_data

    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def create_project_dataset_link(db: Session, link: schemas.ProjectDatasetCreate):
    # Create the link in the association table
    db_link = models.ProjectDataset(**link.model_dump())
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


def create_publication(db: Session, pub: schemas.PublicationCreate):
    db_publication = models.Publication(

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


def link_publication_to_project(db: Session, publication_id: str, project_id: str):
    db_link = models.PublicationHasProject(
        publication_id=publication_id,
        project_id=project_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link
def link_publication_to_dataset(db: Session, publication_id: str, dataset_id: str):
    db_link = models.PublicationHasDataset(
        publication_id=publication_id,
        dataset_id=dataset_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

from sqlalchemy.orm import Session
import models

def get_publication(db: Session, publication_id: int):
    return db.query(models.Publication).options(
        selectinload(models.Publication.datasets),
        selectinload(models.Publication.projects)
    ).filter(models.Publication.id == publication_id).first()


# --- Getters for validation ---
def get_dataset(db: Session, dataset_id: int):
    return db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()

def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()

# --- Link Creators ---
def create_publication_dataset_link(db: Session, publication_id: int, dataset_id: int):
    db_link = models.PublicationHasDataset(
        publication_id=publication_id,
        dataset_id=dataset_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

def create_publication_project_link(db: Session, publication_id: int, project_id: int):
    db_link = models.PublicationHasProject(
        publication_id=publication_id,
        project_id=project_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

def get_publication_dataset_link(db: Session, publication_id: int, dataset_id: int):
    return db.query(models.PublicationHasDataset).filter(
        models.PublicationHasDataset.publication_id == publication_id,
        models.PublicationHasDataset.dataset_id == dataset_id
    ).first()