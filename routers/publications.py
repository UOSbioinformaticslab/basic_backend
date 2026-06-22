from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
from datetime import datetime
import uuid

import schemas
import crud
import models
from database import get_db
# Ensure you import get_current_user from your auth or dependencies module
from dependencies import get_current_user

router = APIRouter(
    prefix="/publications",
    tags=["Publications"]
)


@router.post("/from-doi", response_model=schemas.Publication)
async def create_publication_from_doi(
        request: schemas.DOICreateRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    # --- NEW LOGGING ---
    print("\n" + "=" * 40)
    print(f"📥 RECEIVED POST: PUBLICATION FROM DOI")
    print(f"User: {current_user.name} (ID: {current_user.id})")

    # Check both the token context and the payload context
    # Check both the token context and the payload context
    payload_team_id = request.team_id
    user_team_ids = [team.id for team in current_user.teams]

    print(f"Team ID from Frontend Payload: {payload_team_id}")
    print(f"User's Authorized Team IDs: {user_team_ids}")
    print("=" * 40 + "\n")

    # Determine the target team
    if payload_team_id:
        target_team_id = payload_team_id
    elif len(user_team_ids) == 1:
        # Fallback: If no payload ID is provided but user only has one team, use it
        target_team_id = user_team_ids[0]
    else:
        target_team_id = None

    if not target_team_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Team ID. User belongs to multiple teams, please specify one."
        )

    # Security check: ensure the user actually belongs to the team they are posting to
    if target_team_id not in user_team_ids:
        raise HTTPException(
            status_code=403,
            detail="User is not authorized to post publications for this team."
        )
    # Fetch Crossref metadata
    url = f"https://api.crossref.org/works/{request.doi}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="DOI not found or external API error.")

    data = response.json().get("message", {})

    # Map the Crossref metadata
    title = data.get("title", [""])[0] if data.get("title") else "Unknown Title"
    authors = data.get("author", [])

    published_info = data.get("published-print") or data.get("published-online") or {}
    date_parts = published_info.get("date-parts", [[]])[0]
    year = str(date_parts[0]) if date_parts else "Unknown"

    journal = data.get("container-title", [""])[0] if data.get("container-title") else "Unknown Journal"
    abstract = data.get("abstract", None)
    paper_url = data.get("URL", f"https://doi.org/{request.doi}")

    # Prepare the data
    pub_create_data = schemas.PublicationCreate(
        paper_title=title,
        authors=authors,
        year_of_publication=year,
        paper_doi=data.get("DOI", request.doi),
        journal_name=journal,
        abstract=abstract,
        url=paper_url,
        team_id=target_team_id
    )

    try:
        # Pass the validated target_team_id through to your CRUD function
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
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
    ):
    print("\n" + "=" * 40)
    print(f"📥 RECEIVED GET: PUBLICATION BY ID")
    print(f"User: {current_user.name} (ID: {current_user.id})")
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

    # Validation 2: Do the publication and project share the same team?
    if pub.team_id != project.team_id:
        raise HTTPException(
            status_code=400,
            detail="Team ID mismatch. Publication and Project must belong to the same team."
        )

    try:
        new_link = crud.create_publication_project_link(db, publication_id, project_id)
        return new_link
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to link publication to project: {str(e)}"
        )