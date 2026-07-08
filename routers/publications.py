from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session, selectinload
import httpx
import schemas
import crud
import models
from database import get_db
from dependencies import get_current_user
import traceback

router = APIRouter(
    prefix="/publications",
    tags=["Publications"]
)


@router.get("/", response_model=List[schemas.Publication])
def read_all_publications(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    print("\n" + "=" * 40)
    print("📥 RECEIVED GET: ALL PUBLICATIONS (PUBLIC)")
    print("=" * 40 + "\n")

    # Fetch publications and eager-load the linked collections
    publications = db.query(models.Publication).options(
        selectinload(models.Publication.datasets),
        selectinload(models.Publication.projects)
    ).offset(skip).limit(limit).all()

    return publications

@router.delete("/{publication_id}")
def delete_publication(
        publication_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_publication = db.query(models.Publication).filter(models.Publication.id == publication_id).first()

    if not db_publication:
        raise HTTPException(status_code=404, detail="Publication not found")

    try:
        db.delete(db_publication)
        db.commit()
        return {"message": "Publication successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete publication: {str(e)}"
        )


@router.post("/from-doi", response_model=schemas.Publication)
async def create_publication_from_doi(
        request: schemas.DOICreateRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    print("\n" + "=" * 40)
    print(f"踏 RECEIVED POST: PUBLICATION FROM DOI")
    print(f"User: {current_user.name} (ID: {current_user.id})")

    payload_team_id = request.team_id
    user_team_ids = [team.id for team in current_user.teams]

    print(f"Team ID from Frontend Payload: {payload_team_id}")
    print(f"User's Authorized Team IDs: {user_team_ids}")
    print("=" * 40 + "\n")

    if payload_team_id:
        target_team_id = payload_team_id
    elif len(user_team_ids) == 1:
        target_team_id = user_team_ids[0]
    else:
        target_team_id = None

    if not target_team_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Team ID. User belongs to multiple teams, please specify one."
        )

    if target_team_id not in user_team_ids:
        raise HTTPException(
            status_code=403,
            detail="User is not authorized to post publications for this team."
        )

    # -------------------------------------------------------------------
    # Check if publication already exists in the database
    # -------------------------------------------------------------------
    existing_publication = db.query(models.Publication).filter(models.Publication.paper_doi == request.doi).first()

    if existing_publication:
        print(f"DOI {request.doi} already exists in DB. Returning existing publication.")
        return existing_publication

    # -------------------------------------------------------------------
    # Proceed to fetch from Crossref if it does not exist
    # -------------------------------------------------------------------
    print("Fetching request from crossref")
    url = f"https://api.crossref.org/works/{request.doi}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="DOI not found or external API error.")

    data = response.json().get("message", {})
    print("Got data from Crossref")

    title = data.get("title", [""])[0] if data.get("title") else "Unknown Title"
    author_dict = data.get("author", [])
    if author_dict:
        authors = [f"{author.get('family', author.get('name', ''))}, {author.get('given', '')}".strip(", ") for author in author_dict]
    else:
        authors = []
    print(type(authors[0]))


    published_info = data.get("published-print") or data.get("published-online") or {}
    date_parts = published_info.get("date-parts", [[]])[0]
    year = str(date_parts[0]) if date_parts else "Unknown"

    journal = data.get("container-title", [""])[0] if data.get("container-title") else "Unknown Journal"
    abstract = data.get("abstract", None)
    paper_url = data.get("URL", f"https://doi.org/{request.doi}")
    paper_doi = data.get("DOI", request.doi)

    pub_create_data = schemas.PublicationCreate(
        paper_title=title,
        authors=authors,
        year_of_publication=year,
        paper_doi=paper_doi,
        journal_name=journal,
        abstract=abstract,
        url=paper_url,
        team_id=target_team_id
    )

    try:
        new_publication = crud.create_publication(db=db, pub=pub_create_data)
        return new_publication
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save publication: {str(e)}"
        )

@router.get("/{publication_id}", response_model=schemas.Publication)
def read_publication(
        publication_id: int,
        db: Session = Depends(get_db)
    ):
    print("\n" + "=" * 40)
    print(f"📥 RECEIVED GET: PUBLICATION BY ID")
    print(f"Requested Publication ID: {publication_id}")
    print("=" * 40 + "\n")

    # Fetch the publication from the database
    db_publication = crud.get_publication(db, publication_id=publication_id)

    if db_publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")

    return db_publication


@router.post("/{publication_id}/datasets/{dataset_id}", response_model=schemas.PublicationHasDataset)
def link_publication_to_dataset(
        publication_id: int,
        dataset_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    print("\n" + "=" * 40)
    print(f"📥 RECEIVED POST: LINK PUBLICATION TO DATASET")
    print(f"User: {current_user.name} (ID: {current_user.id})")

    user_team_ids = [team.id for team in current_user.teams]

    # Fetch the records to check their team context
    pub = crud.get_publication(db, publication_id=publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    dataset = crud.get_dataset(db, dataset_id=dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    print(f"Validation Check | User Teams: {user_team_ids} | Pub Team: {pub.team_id} | Dataset Team: {dataset.team_id}")
    print("=" * 40 + "\n")

    # Validation 1: Does the user belong to the publication's team?
    if pub.team_id not in user_team_ids:
        raise HTTPException(
            status_code=403,
            detail="User is not authorized to modify links for this publication's team."
        )

    # Validation 2: Do the publication and dataset share the same team?
    if pub.team_id != dataset.team_id:
        raise HTTPException(
            status_code=400,
            detail="Team ID mismatch. Publication and Dataset must belong to the same team."
        )
        # ... previous validation checks ...

    # Validation 3: Does this link already exist?
    existing_link = crud.get_publication_dataset_link(db, publication_id, dataset_id)
    if existing_link:
        print("link already existed")
        return existing_link
    try:
        new_link = crud.create_publication_dataset_link(db, publication_id, dataset_id)
        return new_link
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to link publication to dataset: {str(e)}"
        )

@router.post("/{publication_id}/projects/{project_id}", response_model=schemas.PublicationHasProject)
def link_publication_to_project(
        publication_id: int,
        project_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    print("\n" + "=" * 40)
    print(f"📥 RECEIVED POST: LINK PUBLICATION TO PROJECT")
    print(f"User: {current_user.name} (ID: {current_user.id})")

    user_team_ids = [team.id for team in current_user.teams]

    # Fetch the records
    pub = crud.get_publication(db, publication_id=publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    project = crud.get_project(db, project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    print(f"Validation Check | User Teams: {user_team_ids} | Pub Team: {pub.team_id} | Project Team: {project.team_id}")
    print("=" * 40 + "\n")

    # Validation 1: Does the user belong to the publication's team?
    if pub.team_id not in user_team_ids:
        raise HTTPException(
            status_code=403,
            detail="User is not authorized to modify links for this publication's team."
        )
    else:
        print("user belongs to publication's team")

    # Validation 2: Do the publication and project share the same team?
    if pub.team_id != project.team_id:
        raise HTTPException(
            status_code=400,
            detail="Team ID mismatch. Publication and Project must belong to the same team."
        )
    else:
        print("publication and project share the same team")

    existing_link = crud.get_publication_project_link(db, publication_id, project_id)
    if existing_link:
        print("link exists")
        return existing_link

    try:
        new_link = crud.create_publication_project_link(db, publication_id, project_id)
        return new_link
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to link publication to dataset: {str(e)}"
        )