# routers/local_sync.py
"""
Local-Only Synchronization and Multi-Environment Dataset Management Router.
This file is listed in .railwayignore and will NOT be deployed to Railway.
It allows local administrators to:
1. List & search datasets across Local, Railway Dev, and Railway Staging.
2. Change dataset team with cascading updates to linked projects, publications, and tools.
3. Delete datasets with cascading deletion of linked projects, publications, and tools.
4. Copy datasets and linked assets between environments with duplicate detection and overwrite confirmation.
"""

import os
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from dotenv import dotenv_values

import models
import schemas
import database
from dependencies import get_current_user

router = APIRouter(prefix="/admin/datasets", tags=["admin-datasets-sync"])

# Dictionary of cached SQLAlchemy engines for each environment
_engines: Dict[str, Any] = {}

def get_env_database_urls() -> Dict[str, Optional[str]]:
    """
    Retrieves database URLs for local, railway_dev, and railway_staging
    directly from the backend .env or environment variables.
    """
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    vals = dotenv_values(env_file) if os.path.exists(env_file) else {}

    urls: Dict[str, Optional[str]] = {
        "local": database.DATABASE_URL,
        "railway_dev": os.environ.get("DEV_DATABASE_PUBLIC_URL") or vals.get("DEV_DATABASE_PUBLIC_URL"),
        "railway_staging": os.environ.get("STAGING_DATABASE_PUBLIC_URL") or vals.get("STAGING_DATABASE_PUBLIC_URL")
    }

    # Normalize PostgreSQL URLs and trim strings
    for key in ["railway_dev", "railway_staging"]:
        u = urls.get(key)
        if u:
            u = u.strip().strip('"').strip("'")
            if u.startswith("postgres://"):
                u = u.replace("postgres://", "postgresql://", 1)
            urls[key] = u

    return urls

def get_engine_for_env(env_name: str):
    """Returns or creates a SQLAlchemy engine for the requested environment."""
    if env_name in _engines:
        return _engines[env_name]

    urls = get_env_database_urls()
    url = urls.get(env_name)
    if not url:
        raise HTTPException(
            status_code=400,
            detail=f"Environment '{env_name}' is not configured with a database URL."
        )

    if "sqlite" in url:
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            connect_args={"connect_timeout": 10}
        )

    _engines[env_name] = engine
    return engine

@contextmanager
def get_db_for_env(env_name: str):
    """Context manager yielding a SQLAlchemy Session for a specific environment."""
    engine = get_engine_for_env(env_name)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def extract_dataset_title(dataset: models.Dataset) -> str:
    """Extracts computed or summary title from dataset."""
    if isinstance(dataset.metadata_blob, dict):
        summary = dataset.metadata_blob.get("summary", {})
        if isinstance(summary, dict) and summary.get("title"):
            return str(summary.get("title"))
    if isinstance(dataset.draft_metadata_blob, dict):
        summary = dataset.draft_metadata_blob.get("summary", {})
        if isinstance(summary, dict) and summary.get("title"):
            return str(summary.get("title"))
    return f"Dataset {dataset.id}"


# --- REQUEST & RESPONSE SCHEMAS ---

class TeamUpdatePayload(BaseModel):
    team_id: int

class DatasetCopyPayload(BaseModel):
    dataset_id: int
    source_env: str = "local"
    target_env: str
    overwrite: bool = False


# --- ENDPOINTS ---

@router.get("/environments")
def get_environments(current_user: models.User = Depends(get_current_user)):
    """Returns available environments and their connection configuration status."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    urls = get_env_database_urls()
    return {
        "is_local": True,
        "environments": [
            {"id": "local", "name": "Local (SQLite)", "configured": bool(urls.get("local")), "is_current": True},
            {"id": "railway_dev", "name": "Railway Dev", "configured": bool(urls.get("railway_dev")), "is_current": False},
            {"id": "railway_staging", "name": "Railway Staging", "configured": bool(urls.get("railway_staging")), "is_current": False}
        ]
    }


@router.get("/teams")
def get_environment_teams(
    env: str = Query("local", description="Environment: local, railway_dev, or railway_staging"),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns all teams for the specified environment to populate team filters and team reassignment dropdowns.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    with get_db_for_env(env) as db:
        teams = db.query(models.Team.id, models.Team.name).order_by(models.Team.name.asc()).all()
        team_list = [{"id": t.id, "name": t.name} for t in teams]
        return {"teams": team_list, "total": len(team_list)}


@router.get("")
def list_datasets(
    env: str = Query("local", description="Environment: local, railway_dev, or railway_staging"),
    search: Optional[str] = Query(None, description="Search term for title, team, or datasetid"),
    team_id: Optional[int] = Query(None, description="Filter by team ID"),
    current_user: models.User = Depends(get_current_user)
):
    """
    Lists all datasets from the specified environment.
    Computes title, team name, and counts of linked projects, publications, and tools.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        with get_db_for_env(env) as db:
            from sqlalchemy import func
            from sqlalchemy.orm import defer

            # Pre-fetch counts in single batch queries instead of N+1 lazy queries
            proj_counts = dict(
                db.query(models.ProjectDataset.dataset_id, func.count(models.ProjectDataset.id))
                .group_by(models.ProjectDataset.dataset_id).all()
            )
            pub_counts = dict(
                db.query(models.PublicationHasDataset.dataset_id, func.count(models.PublicationHasDataset.publication_id))
                .group_by(models.PublicationHasDataset.dataset_id).all()
            )
            tool_counts = dict(
                db.query(models.ToolHasDataset.dataset_id, func.count(models.ToolHasDataset.tool_id))
                .group_by(models.ToolHasDataset.dataset_id).all()
            )

            # Pre-fetch team names in 1 fast query
            teams = {t.id: t.name for t in db.query(models.Team.id, models.Team.name).all()}

            # Defer heavy draft blobs so only necessary metadata is transferred
            query = db.query(models.Dataset).options(defer(models.Dataset.draft_metadata_blob))
            if team_id:
                query = query.filter(models.Dataset.team_id == team_id)

            all_datasets = query.order_by(models.Dataset.id.desc()).all()

            results = []
            for ds in all_datasets:
                title = extract_dataset_title(ds)
                team_name = teams.get(ds.team_id) or (f"Team {ds.team_id}" if ds.team_id else "Unassigned")
                ds_identifier = ds.datasetid or f"DS-{ds.id}"

                # Filter by search string if provided
                if search:
                    term = search.strip().lower()
                    matches = (
                        term in title.lower() or
                        term in ds_identifier.lower() or
                        term in team_name.lower() or
                        term == str(ds.id)
                    )
                    if not matches:
                        continue

                results.append({
                    "id": ds.id,
                    "datasetid": ds.datasetid,
                    "title": title,
                    "team_id": ds.team_id,
                    "team_name": team_name,
                    "status": ds.status or ("ACTIVE" if ds.active else "DRAFT"),
                    "active": bool(ds.active),
                    "created_at": ds.created_at.isoformat() if ds.created_at else None,
                    "linked_projects_count": proj_counts.get(ds.id, 0),
                    "linked_publications_count": pub_counts.get(ds.id, 0),
                    "linked_tools_count": tool_counts.get(ds.id, 0)
                })

            return {
                "environment": env,
                "total": len(results),
                "datasets": results
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query database for '{env}': {str(e)}"
        )


@router.put("/{dataset_id}/team")
def change_dataset_team(
    dataset_id: int,
    payload: TeamUpdatePayload,
    env: str = Query("local", description="Target environment"),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates the team for a dataset and cascades the team_id update
    to all associated projects, publications, and tools.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    with get_db_for_env(env) as db:
        dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found in {env}")

        target_team = db.query(models.Team).filter(models.Team.id == payload.team_id).first()
        if not target_team:
            raise HTTPException(status_code=404, detail=f"Team {payload.team_id} not found in {env}")

        # Update dataset team
        dataset.team_id = payload.team_id
        dataset.updated_at = datetime.now(timezone.utc)

        # Cascade update to linked projects
        project_links = db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == dataset.id).all()
        updated_projects = 0
        for pl in project_links:
            if pl.project:
                pl.project.team_id = payload.team_id
                updated_projects += 1

        # Cascade update to linked publications
        pub_links = db.query(models.PublicationHasDataset).filter(models.PublicationHasDataset.dataset_id == dataset.id).all()
        updated_pubs = 0
        for pub_link in pub_links:
            pub = db.query(models.Publication).filter(models.Publication.id == pub_link.publication_id).first()
            if pub:
                pub.team_id = payload.team_id
                updated_pubs += 1

        # Cascade update to linked tools
        tool_links = db.query(models.ToolHasDataset).filter(models.ToolHasDataset.dataset_id == dataset.id).all()
        updated_tools = 0
        for tl in tool_links:
            tool = db.query(models.Tool).filter(models.Tool.id == tl.tool_id).first()
            if tool:
                tool.team_id = payload.team_id
                updated_tools += 1

        db.commit()

        return {
            "message": f"Dataset team successfully changed to '{target_team.name}'",
            "dataset_id": dataset.id,
            "new_team_id": payload.team_id,
            "new_team_name": target_team.name,
            "updated_projects": updated_projects,
            "updated_publications": updated_pubs,
            "updated_tools": updated_tools
        }


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    env: str = Query("local", description="Target environment"),
    current_user: models.User = Depends(get_current_user)
):
    """
    Deletes a dataset and automatically deletes all associated projects, publications,
    and tools linked to it.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    with get_db_for_env(env) as db:
        dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found in {env}")

        dataset_title = extract_dataset_title(dataset)

        # 1. Identify linked entities
        project_links = db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == dataset.id).all()
        projects_to_delete = [pl.project for pl in project_links if pl.project]

        pub_links = db.query(models.PublicationHasDataset).filter(models.PublicationHasDataset.dataset_id == dataset.id).all()
        pubs_to_delete = [
            db.query(models.Publication).filter(models.Publication.id == pbl.publication_id).first()
            for pbl in pub_links
        ]
        pubs_to_delete = [p for p in pubs_to_delete if p]

        tool_links = db.query(models.ToolHasDataset).filter(models.ToolHasDataset.dataset_id == dataset.id).all()
        tools_to_delete = [
            db.query(models.Tool).filter(models.Tool.id == tl.tool_id).first()
            for tl in tool_links
        ]
        tools_to_delete = [t for t in tools_to_delete if t]

        # 2. Delete association records
        db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == dataset.id).delete()
        db.query(models.PublicationHasDataset).filter(models.PublicationHasDataset.dataset_id == dataset.id).delete()
        db.query(models.ToolHasDataset).filter(models.ToolHasDataset.dataset_id == dataset.id).delete()

        # 3. Clean up linked projects and their secondary links
        for p in projects_to_delete:
            db.query(models.PublicationHasProject).filter(models.PublicationHasProject.project_id == p.id).delete()
            db.query(models.ToolHasProject).filter(models.ToolHasProject.project_id == p.id).delete()
            db.delete(p)

        # 4. Clean up linked publications and their secondary links
        for pub in pubs_to_delete:
            db.query(models.PublicationHasTool).filter(models.PublicationHasTool.publication_id == pub.id).delete()
            db.delete(pub)

        # 5. Clean up linked tools
        for t in tools_to_delete:
            db.delete(t)

        # 6. Delete the dataset itself
        db.delete(dataset)
        db.commit()

        return {
            "message": f"Dataset '{dataset_title}' and all linked assets successfully deleted.",
            "deleted_dataset_id": dataset_id,
            "deleted_projects_count": len(projects_to_delete),
            "deleted_publications_count": len(pubs_to_delete),
            "deleted_tools_count": len(tools_to_delete)
        }


@router.post("/copy")
def copy_dataset(
    payload: DatasetCopyPayload,
    current_user: models.User = Depends(get_current_user)
):
    """
    Copies a dataset and all linked projects, publications, and tools from source_env to target_env.
    Non-destructive: Source records are NOT deleted.
    Detects if the dataset already exists on target; if so, requires overwrite=True.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    if payload.source_env == payload.target_env:
        raise HTTPException(status_code=400, detail="Source and target environments must be different.")

    with get_db_for_env(payload.source_env) as src_db, get_db_for_env(payload.target_env) as tgt_db:
        # 1. Fetch dataset from source
        src_ds = src_db.query(models.Dataset).filter(models.Dataset.id == payload.dataset_id).first()
        if not src_ds:
            raise HTTPException(status_code=404, detail=f"Dataset {payload.dataset_id} not found in {payload.source_env}")

        src_title = extract_dataset_title(src_ds)
        src_datasetid = src_ds.datasetid

        # 2. Check for duplicate on target database
        existing_tgt_ds = None
        if src_datasetid:
            existing_tgt_ds = tgt_db.query(models.Dataset).filter(models.Dataset.datasetid == src_datasetid).first()

        if not existing_tgt_ds:
            # Check by title in metadata_blob
            for tgt_candidate in tgt_db.query(models.Dataset).all():
                if extract_dataset_title(tgt_candidate).strip().lower() == src_title.strip().lower():
                    existing_tgt_ds = tgt_candidate
                    break

        if existing_tgt_ds and not payload.overwrite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "conflict": True,
                    "message": f"A dataset with title '{src_title}' or ID '{src_datasetid}' already exists in {payload.target_env}.",
                    "target_dataset_id": existing_tgt_ds.id,
                    "target_dataset_title": extract_dataset_title(existing_tgt_ds)
                }
            )

        # 3. Reconcile Target Team
        tgt_team = None
        tgt_team_id = None
        if src_ds.team_id:
            src_team = src_db.query(models.Team).filter(models.Team.id == src_ds.team_id).first()
            if src_team:
                if src_team.name:
                    tgt_team = tgt_db.query(models.Team).filter(models.Team.name == src_team.name).first()
                if not tgt_team:
                    tgt_team = models.Team(
                        name=src_team.name,
                        notification_email=src_team.notification_email,
                        hdr_gateway_email=src_team.hdr_gateway_email,
                        introduction=src_team.introduction,
                        url=src_team.url
                    )
                    tgt_db.add(tgt_team)
                    tgt_db.flush()
                # If found but some details differ: do not update existing details
                tgt_team_id = tgt_team.id

        # 4. Reconcile Target User
        tgt_user = None
        tgt_user_id = None
        if src_ds.user_id:
            src_user = src_db.query(models.User).filter(models.User.id == src_ds.user_id).first()
            if src_user:
                # Search target for existing user matching name (or email)
                if src_user.name:
                    tgt_user = tgt_db.query(models.User).filter(models.User.name == src_user.name).first()
                if not tgt_user and src_user.email:
                    tgt_user = tgt_db.query(models.User).filter(models.User.email == src_user.email).first()

                if not tgt_user:
                    tgt_user = models.User(
                        name=src_user.name,
                        email=src_user.email,
                        hashed_password=src_user.hashed_password,
                        applicant_organisation=src_user.applicant_organisation,
                        is_admin=bool(src_user.is_admin)
                    )
                    tgt_db.add(tgt_user)
                    tgt_db.flush()
                # If found but some details differ: do not update existing details
                tgt_user_id = tgt_user.id

        if not tgt_user_id:
            admin_user = tgt_db.query(models.User).filter(models.User.is_admin == True).first()
            if admin_user:
                tgt_user = admin_user
                tgt_user_id = admin_user.id
            else:
                first_user = tgt_db.query(models.User).first()
                if first_user:
                    tgt_user = first_user
                    tgt_user_id = first_user.id

        # 4.1 Link User to Team in user_teams if not already linked
        if tgt_team and tgt_user:
            is_member = tgt_db.query(models.user_teams).filter(
                models.user_teams.c.user_id == tgt_user.id,
                models.user_teams.c.team_id == tgt_team.id
            ).first()
            if not is_member:
                src_is_team_admin = False
                if src_ds.team_id and src_ds.user_id:
                    src_mem = src_db.query(models.user_teams).filter(
                        models.user_teams.c.user_id == src_ds.user_id,
                        models.user_teams.c.team_id == src_ds.team_id
                    ).first()
                    if src_mem and hasattr(src_mem, 'is_team_admin'):
                        src_is_team_admin = bool(src_mem.is_team_admin)

                tgt_db.execute(
                    models.user_teams.insert().values(
                        user_id=tgt_user.id,
                        team_id=tgt_team.id,
                        is_team_admin=src_is_team_admin
                    )
                )
                tgt_db.flush()

        # 5. Insert or Update Dataset in Target
        if existing_tgt_ds and payload.overwrite:
            target_ds = existing_tgt_ds
            target_ds.metadata_blob = src_ds.metadata_blob
            target_ds.draft_metadata_blob = src_ds.draft_metadata_blob
            target_ds.active = src_ds.active
            target_ds.status = src_ds.status
            target_ds.team_id = tgt_team_id or target_ds.team_id
            target_ds.user_id = tgt_user_id or target_ds.user_id
            target_ds.updated_at = datetime.now(timezone.utc)
            # Clear old association links in target for clean re-linking
            tgt_db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == target_ds.id).delete()
            tgt_db.query(models.PublicationHasDataset).filter(models.PublicationHasDataset.dataset_id == target_ds.id).delete()
            tgt_db.query(models.ToolHasDataset).filter(models.ToolHasDataset.dataset_id == target_ds.id).delete()
        else:
            target_ds = models.Dataset(
                datasetid=src_datasetid,
                metadata_blob=src_ds.metadata_blob,
                draft_metadata_blob=src_ds.draft_metadata_blob,
                active=src_ds.active,
                status=src_ds.status,
                team_id=tgt_team_id,
                user_id=tgt_user_id,
                created_at=src_ds.created_at or datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            tgt_db.add(target_ds)
            tgt_db.flush()

            # Ensure metadata_blob reflects the target database internal ID
            if isinstance(target_ds.metadata_blob, dict):
                blob_copy = dict(target_ds.metadata_blob)
                blob_copy["id"] = target_ds.id
                target_ds.metadata_blob = blob_copy
            if isinstance(target_ds.draft_metadata_blob, dict):
                draft_copy = dict(target_ds.draft_metadata_blob)
                draft_copy["id"] = target_ds.id
                target_ds.draft_metadata_blob = draft_copy
            tgt_db.flush()

        # 6. Copy Linked Projects
        copied_projects = 0
        src_project_links = src_db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == src_ds.id).all()
        for pl in src_project_links:
            if not pl.project:
                continue
            src_proj = pl.project
            # Find or create project in target by PID
            tgt_proj = None
            if src_proj.pid:
                tgt_proj = tgt_db.query(models.Project).filter(models.Project.pid == src_proj.pid).first()

            if tgt_proj:
                if not tgt_proj.team_id and tgt_team_id:
                    tgt_proj.team_id = tgt_team_id
                if not tgt_proj.user_id and tgt_user_id:
                    tgt_proj.user_id = tgt_user_id
            else:
                tgt_proj = models.Project(
                    pid=src_proj.pid,
                    version=src_proj.version,
                    project_grant_name=src_proj.project_grant_name,
                    lead_researcher=src_proj.lead_researcher,
                    lead_research_institute=src_proj.lead_research_institute,
                    grant_numbers=src_proj.grant_numbers,
                    project_grant_start_date=src_proj.project_grant_start_date,
                    project_grant_end_date=src_proj.project_grant_end_date,
                    project_grant_scope=src_proj.project_grant_scope,
                    metadata_blob=src_proj.metadata_blob,
                    status=src_proj.status,
                    team_id=tgt_team_id,
                    user_id=tgt_user_id
                )
                tgt_db.add(tgt_proj)
                tgt_db.flush()

            # Ensure ProjectDataset link in target
            tgt_link = tgt_db.query(models.ProjectDataset).filter(
                models.ProjectDataset.project_id == tgt_proj.id,
                models.ProjectDataset.dataset_id == target_ds.id
            ).first()
            if not tgt_link:
                tgt_db.add(models.ProjectDataset(project_id=tgt_proj.id, dataset_id=target_ds.id))
            copied_projects += 1

        # 7. Copy Linked Publications
        copied_pubs = 0
        src_pub_links = src_db.query(models.PublicationHasDataset).filter(models.PublicationHasDataset.dataset_id == src_ds.id).all()
        for pub_link in src_pub_links:
            src_pub = src_db.query(models.Publication).filter(models.Publication.id == pub_link.publication_id).first()
            if not src_pub:
                continue

            tgt_pub = None
            if src_pub.paper_doi:
                tgt_pub = tgt_db.query(models.Publication).filter(models.Publication.paper_doi == src_pub.paper_doi).first()

            if tgt_pub:
                if not tgt_pub.team_id and tgt_team_id:
                    tgt_pub.team_id = tgt_team_id
            else:
                tgt_pub = models.Publication(
                    paper_title=src_pub.paper_title,
                    authors=src_pub.authors,
                    year_of_publication=src_pub.year_of_publication,
                    paper_doi=src_pub.paper_doi,
                    journal_name=src_pub.journal_name,
                    abstract=src_pub.abstract,
                    url=src_pub.url,
                    team_id=tgt_team_id
                )
                tgt_db.add(tgt_pub)
                tgt_db.flush()

            tgt_pub_link = tgt_db.query(models.PublicationHasDataset).filter(
                models.PublicationHasDataset.publication_id == tgt_pub.id,
                models.PublicationHasDataset.dataset_id == target_ds.id
            ).first()
            if not tgt_pub_link:
                tgt_db.add(models.PublicationHasDataset(publication_id=tgt_pub.id, dataset_id=target_ds.id))
            copied_pubs += 1

        # 8. Copy Linked Tools
        copied_tools = 0
        src_tool_links = src_db.query(models.ToolHasDataset).filter(models.ToolHasDataset.dataset_id == src_ds.id).all()
        for tl in src_tool_links:
            src_tool = src_db.query(models.Tool).filter(models.Tool.id == tl.tool_id).first()
            if not src_tool:
                continue

            tgt_tool = None
            if src_tool.name:
                tgt_tool = tgt_db.query(models.Tool).filter(models.Tool.name == src_tool.name).first()

            if tgt_tool:
                if not tgt_tool.team_id and tgt_team_id:
                    tgt_tool.team_id = tgt_team_id
                if not tgt_tool.user_id and tgt_user_id:
                    tgt_tool.user_id = tgt_user_id
            else:
                tgt_tool = models.Tool(
                    name=src_tool.name,
                    url=src_tool.url,
                    description=src_tool.description,
                    results_insights=src_tool.results_insights,
                    license=src_tool.license,
                    tech_stack=src_tool.tech_stack,
                    category_id=src_tool.category_id,
                    enabled=src_tool.enabled,
                    status=src_tool.status,
                    team_id=tgt_team_id,
                    user_id=tgt_user_id
                )
                tgt_db.add(tgt_tool)
                tgt_db.flush()

            tgt_tool_link = tgt_db.query(models.ToolHasDataset).filter(
                models.ToolHasDataset.tool_id == tgt_tool.id,
                models.ToolHasDataset.dataset_id == target_ds.id
            ).first()
            if not tgt_tool_link:
                tgt_db.add(models.ToolHasDataset(tool_id=tgt_tool.id, dataset_id=target_ds.id))
            copied_tools += 1

        # Commit target DB. Source DB is left completely untouched.
        tgt_db.commit()

        return {
            "message": f"Successfully copied '{src_title}' from {payload.source_env} to {payload.target_env}.",
            "target_dataset_id": target_ds.id,
            "target_dataset_identifier": target_ds.datasetid,
            "target_team_id": tgt_team_id,
            "target_user_id": tgt_user_id,
            "copied_projects": copied_projects,
            "copied_publications": copied_pubs,
            "copied_tools": copied_tools
        }
