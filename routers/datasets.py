# routers/datasets.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import String, func
import uuid
from datetime import datetime

# Standard Absolute Imports

from dependencies import get_current_user, get_current_admin_user
import database, schemas, models, crud
router = APIRouter(prefix="/datasets", tags=["datasets"])

def build_dataset_response(db_dataset: models.Dataset, use_draft: bool = False) -> dict:
    blob = db_dataset.draft_metadata_blob if (use_draft and db_dataset.draft_metadata_blob is not None) else db_dataset.metadata_blob
    if blob is None and db_dataset.draft_metadata_blob is not None:
        blob = db_dataset.draft_metadata_blob

    # Build linked projects list
    projects_list = []
    if getattr(db_dataset, 'projects', None):
        for p in db_dataset.projects:
            p_name = p.project_grant_name
            if not p_name and isinstance(p.metadata_blob, dict):
                p_name = p.metadata_blob.get("summary", {}).get("title") or p.metadata_blob.get("project_grant_name")
            projects_list.append({
                "id": p.id,
                "pid": p.pid,
                "project_grant_name": p_name or f"Project {p.id}",
                "lead_researcher": p.lead_researcher,
                "lead_research_institute": p.lead_research_institute,
                "grant_numbers": p.grant_numbers,
                "project_grant_start_date": p.project_grant_start_date,
                "project_grant_end_date": p.project_grant_end_date,
                "project_grant_scope": p.project_grant_scope,
                "status": p.status
            })

    # Build linked publications list
    publications_list = []
    if getattr(db_dataset, 'publications', None):
        for pub in db_dataset.publications:
            publications_list.append({
                "id": pub.id,
                "paper_title": pub.paper_title or "Untitled Publication",
                "year_of_publication": pub.year_of_publication,
                "paper_doi": pub.paper_doi,
                "journal_name": pub.journal_name,
                "url": pub.url,
                "authors": pub.authors or []
            })

    # Build linked tools list
    tools_list = []
    if getattr(db_dataset, 'tools', None):
        for t in db_dataset.tools:
            tools_list.append({
                "id": t.id,
                "name": t.name or f"Tool {t.id}",
                "url": t.url,
                "description": t.description,
                "status": t.status,
                "enabled": t.enabled,
                "team_id": t.team_id
            })

    return {
        "id": db_dataset.id,
        "datasetid": db_dataset.datasetid,
        "metadata_blob": blob or {},
        "draft_metadata_blob": db_dataset.draft_metadata_blob,
        "team_id": db_dataset.team_id,
        "team_name": db_dataset.team.name if db_dataset.team else None,
        "status": db_dataset.status,
        "active": bool(db_dataset.active),
        "has_draft": db_dataset.draft_metadata_blob is not None,
        "created_at": db_dataset.created_at,
        "projects": projects_list,
        "publications": publications_list,
        "tools": tools_list
    }


@router.get("/", response_model=List[schemas.DatasetResponse])
def list_all_datasets(db: Session = Depends(database.get_db)):
    """
    Publicly accessible route to view all ACTIVE datasets.
    Does NOT require a JWT token.
    """
    active_datasets = db.query(models.Dataset).filter(models.Dataset.active == True).all()
    return [build_dataset_response(ds) for ds in active_datasets]


@router.get("/filters")
def get_all_filters(db: Session = Depends(database.get_db)):
    """
    Returns the complete taxonomy filter dictionary from the database,
    keyed by filter ID string.
    """
    filter_records = db.query(models.Filter).all()
    result = {}
    for f in filter_records:
        result[f.id] = {
            "id": f.id,
            "label": f.label,
            "category": f.category,
            "primaryGroup": f.primaryGroup,
            "description": f.description or "",
            "parentId": f.parentId,
            "path": f.path or []
        }
    return result


@router.get("/search", response_model=List[schemas.DatasetResponse])
def search_datasets(
        title: str,
        db: Session = Depends(database.get_db)
):
    """
    Search for active datasets by checking the specific summary.title path.
    """
    search_term = f"%{title}%"

    datasets = db.query(models.Dataset).filter(
        models.Dataset.active == True,
        func.json_extract(models.Dataset.metadata_blob, '$.summary.title').ilike(search_term)
    ).all()

    return [build_dataset_response(ds) for ds in datasets]


@router.get("/list/simple", response_model=List[schemas.DatasetSimpleResponse])
def get_simple_dataset_list(
    team_id: int = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Query all dataset records so editors can see drafts and active records
    query = db.query(
        models.Dataset.id,
        models.Dataset.datasetid,
        models.Dataset.metadata_blob,
        models.Dataset.draft_metadata_blob,
        models.Dataset.active
    )
    
    if team_id:
        if not current_user.is_admin and team_id not in [t.id for t in current_user.teams]:
            raise HTTPException(status_code=403, detail="Not in this team")
        query = query.filter(models.Dataset.team_id == team_id)
    elif not current_user.is_admin:
        team_ids = [t.id for t in current_user.teams]
        query = query.filter(models.Dataset.team_id.in_(team_ids))
        
    records = query.all()

    results = []
    for record in records:
        # Prefer draft title if present, otherwise active title
        blob = record.draft_metadata_blob if record.draft_metadata_blob is not None else record.metadata_blob
        title = f"Dataset {record.id}"
        if isinstance(blob, dict):
            title = blob.get("summary", {}).get("title", title)

        results.append({
            "id": record.id,
            "datasetid": record.datasetid,
            "computed_title": title,
            "active": bool(record.active),
            "has_draft": record.draft_metadata_blob is not None
        })
    return results


@router.get("/team/{team_id}/linkable")
def get_team_linkable_datasets(
    team_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_admin and team_id not in [t.id for t in current_user.teams]:
        raise HTTPException(status_code=403, detail="Not a member of this team")

    records = db.query(models.Dataset).filter(models.Dataset.team_id == team_id).all()

    # Group datasets by logical identity
    grouped = {}
    for r in records:
        blob = r.draft_metadata_blob if r.draft_metadata_blob is not None else r.metadata_blob
        title = None
        if isinstance(blob, dict):
            title = blob.get("summary", {}).get("title")
        if not title:
            title = r.computed_title or r.datasetid or f"Dataset {r.id}"

        key = r.datasetid if r.datasetid else title.strip().lower()
        if key not in grouped:
            grouped[key] = []
        grouped[key].append((r, title))

    linkable = []
    for key, items in grouped.items():
        active_items = [item for item in items if item[0].active]
        if active_items:
            chosen = max(active_items, key=lambda x: (x[0].updated_at or x[0].created_at or datetime.min, x[0].id))
        else:
            chosen = max(items, key=lambda x: (x[0].updated_at or x[0].created_at or datetime.min, x[0].id))

        rec, title = chosen
        linkable.append({
            "id": rec.id,
            "datasetid": rec.datasetid,
            "title": title,
            "active": bool(rec.active),
            "status": rec.status
        })

    linkable.sort(key=lambda x: (x["title"] or "").lower())
    return linkable


@router.get("/{dataset_id}", response_model=schemas.DatasetResponse)
def get_public_dataset(
        dataset_id: str,
        preview: bool = False,
        db: Session = Depends(database.get_db)
):
    # Look up the dataset by primary key ID or datasetid string with eager loading
    query = db.query(models.Dataset).options(
        selectinload(models.Dataset.projects),
        selectinload(models.Dataset.publications),
        selectinload(models.Dataset.tools),
        selectinload(models.Dataset.team)
    )

    db_dataset = None
    if str(dataset_id).isdigit():
        db_dataset = query.filter(models.Dataset.id == int(dataset_id)).first()
    if not db_dataset:
        db_dataset = query.filter(models.Dataset.datasetid == str(dataset_id)).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # If dataset is not active and not in preview mode, hide it from public view
    if not db_dataset.active and not preview:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return build_dataset_response(db_dataset, use_draft=preview)


@router.post("/", response_model=schemas.DatasetResponse)
def save_metadata_progress(
        dataset_in: schemas.DatasetBase,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    payload_team_id = dataset_in.team_id
    unique_ds_id = f"DS-{uuid.uuid4().hex[:8].upper()}"
    target_team_id = payload_team_id

    if not target_team_id:
        raise HTTPException(status_code=400, detail="Missing Team ID context")

    user_team_ids = [team.id for team in current_user.teams]
    if target_team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the specified team")

    dependencies.enforce_non_sandbox(db, target_team_id, "Creating datasets")

    is_active = bool(dataset_in.active or dataset_in.status == models.Dataset.STATUS_ACTIVE)

    db_dataset = models.Dataset(
        metadata_blob=dataset_in.metadata_blob if is_active else {},
        draft_metadata_blob=None if is_active else dataset_in.metadata_blob,
        datasetid=unique_ds_id,
        user_id=current_user.id,
        team_id=dataset_in.team_id,
        active=is_active,
        status=models.Dataset.STATUS_ACTIVE if is_active else models.Dataset.STATUS_DRAFT,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        db.add(db_dataset)
        db.commit()
        db.refresh(db_dataset)

        # Synchronize linked projects if provided
        if dataset_in.project_ids is not None:
            for pid in dataset_in.project_ids:
                db.add(models.ProjectDataset(project_id=pid, dataset_id=db_dataset.id))
            db.commit()

        # Reload with relationships
        db_dataset = db.query(models.Dataset).options(
            selectinload(models.Dataset.projects),
            selectinload(models.Dataset.publications),
            selectinload(models.Dataset.tools),
            selectinload(models.Dataset.team)
        ).filter(models.Dataset.id == db_dataset.id).first()

        return build_dataset_response(db_dataset, use_draft=not is_active)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save metadata: {str(e)}"
        )


@router.put("/{dataset_id}", response_model=schemas.DatasetResponse)
def update_metadata_progress(
        dataset_id: str,
        dataset_in: schemas.DatasetBase,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_dataset = None
    if str(dataset_id).isdigit():
        db_dataset = db.query(models.Dataset).filter(models.Dataset.id == int(dataset_id)).first()
    if not db_dataset:
        db_dataset = db.query(models.Dataset).filter(models.Dataset.datasetid == str(dataset_id)).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dependencies.enforce_non_sandbox(db, db_dataset.team_id, "Updating datasets")

    if dataset_in.team_id:
        user_team_ids = [team.id for team in current_user.teams]
        if dataset_in.team_id not in user_team_ids:
            raise HTTPException(status_code=403, detail="User is not a member of the specified team")
        dependencies.enforce_non_sandbox(db, dataset_in.team_id, "Updating datasets")
        db_dataset.team_id = dataset_in.team_id

    # Check for unpublish request
    if dataset_in.unpublish:
        db_dataset.active = False
        db_dataset.status = models.Dataset.STATUS_DRAFT
    elif dataset_in.active or dataset_in.status == models.Dataset.STATUS_ACTIVE:
        # Publish/Make Active: promote draft data (or payload) to live metadata_blob
        incoming_blob = dataset_in.metadata_blob or db_dataset.draft_metadata_blob or db_dataset.metadata_blob
        db_dataset.metadata_blob = incoming_blob
        db_dataset.draft_metadata_blob = None
        db_dataset.active = True
        db_dataset.status = models.Dataset.STATUS_ACTIVE
    else:
        # Save as Draft
        if db_dataset.active:
            # Record is already published: save new edits as working draft
            db_dataset.draft_metadata_blob = dataset_in.metadata_blob
        else:
            # Record is currently draft only
            db_dataset.metadata_blob = dataset_in.metadata_blob
            db_dataset.draft_metadata_blob = None
            db_dataset.active = False
            db_dataset.status = models.Dataset.STATUS_DRAFT

    try:
        # Synchronize linked projects if provided
        if dataset_in.project_ids is not None:
            db.query(models.ProjectDataset).filter(models.ProjectDataset.dataset_id == db_dataset.id).delete()
            for pid in dataset_in.project_ids:
                db.add(models.ProjectDataset(project_id=pid, dataset_id=db_dataset.id))

        db.commit()

        # Reload with relationships
        db_dataset = db.query(models.Dataset).options(
            selectinload(models.Dataset.projects),
            selectinload(models.Dataset.publications),
            selectinload(models.Dataset.tools),
            selectinload(models.Dataset.team)
        ).filter(models.Dataset.id == db_dataset.id).first()

        return build_dataset_response(db_dataset, use_draft=not db_dataset.active)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update metadata: {str(e)}"
        )

@router.post("/{dataset_id}/links/{project_id}", response_model=schemas.ProjectDatasetResponse)
async def link_to_project(
        dataset_id: int,
        project_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Check if the dataset exists
    db_dataset = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 2. Check if the project exists
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    dependencies.enforce_non_sandbox(db, db_dataset.team_id, "Linking datasets")
    dependencies.enforce_non_sandbox(db, db_project.team_id, "Linking projects")

    # 3. Check for an existing link to avoid unique constraint errors
    existing = db.query(models.ProjectDataset).filter(
        models.ProjectDataset.dataset_id == dataset_id,
        models.ProjectDataset.project_id == project_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    # 4. Create the link using the new crud function
    link_data = schemas.ProjectDatasetCreate(project_id=project_id, dataset_id=dataset_id)
    return crud.create_project_dataset_link(db, link_data)


@router.delete("/{dataset_id}/links/{project_id}")
async def unlink_from_project(
        dataset_id: int,
        project_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    link = db.query(models.ProjectDataset).filter(
        models.ProjectDataset.dataset_id == dataset_id,
        models.ProjectDataset.project_id == project_id
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Link between dataset and project not found")

    db_dataset = crud.get_dataset(db, dataset_id=dataset_id)
    db_project = crud.get_project(db, project_id=project_id)
    if db_dataset:
        dependencies.enforce_non_sandbox(db, db_dataset.team_id, "Unlinking datasets")
    if db_project:
        dependencies.enforce_non_sandbox(db, db_project.team_id, "Unlinking projects")

    try:
        db.delete(link)
        db.commit()
        return {"message": "Link successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete link: {str(e)}")


@router.delete("/{dataset_id}")
def delete_dataset(
        dataset_id: str,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_dataset = None
    if str(dataset_id).isdigit():
        db_dataset = db.query(models.Dataset).filter(models.Dataset.id == int(dataset_id)).first()
    if not db_dataset:
        db_dataset = db.query(models.Dataset).filter(models.Dataset.datasetid == str(dataset_id)).first()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dependencies.enforce_non_sandbox(db, db_dataset.team_id, "Deleting datasets")

    try:
        db.delete(db_dataset)
        db.commit()
        return {"message": "Dataset successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete dataset: {str(e)}"
        )


@router.get("/extra-terms/{mapping_id}", response_model=schemas.CancerTermMappingResponse)
def get_extra_term_by_id(
        mapping_id: int,
        db: Session = Depends(database.get_db)
):
    """
    Retrieve a specific cancer term mapping record by its primary key ID.
    """
    record = db.query(models.CancerTermMapping).filter(
        models.CancerTermMapping.id == mapping_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Mapping record not found")

    return record


@router.post("/extra-terms/record", response_model=schemas.CancerTermMappingResponse)
def post_new_extra_term(
        payload: schemas.CancerTermMappingCreate,
        db: Session = Depends(database.get_db),
        current_admin: models.User = Depends(get_current_admin_user),
):
    """
    Insert a new cancer term mapping record into the standalone database table.
    """
    db_record = models.CancerTermMapping(
        topography=payload.topography,
        histology=payload.histology,
        associated_terms=payload.associated_terms
    )

    try:
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        return db_record
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database insertion failed: {str(e)}"
        )

@router.post("/extra-terms")
def get_matching_terms(
        req: schemas.LookupRequest,
        db: Session = Depends(database.get_db)
):
    """
    Given a list of topography and histology IDs (or labels), returns a nested
    mapping dictionary containing matching supplementary ontology records,
    hydrating full filter objects looked up directly from the database 'filters' table.
    """
    topo_ids = req.topography_ids or []
    hist_ids = req.histology_ids or []

    # If label strings are provided instead of IDs, resolve labels to IDs via 'filters' table
    if not topo_ids and req.topographies:
        topo_filters = db.query(models.Filter).filter(models.Filter.label.in_(req.topographies)).all()
        topo_ids = [f.id for f in topo_filters]

    if not hist_ids and req.histologies:
        hist_filters = db.query(models.Filter).filter(models.Filter.label.in_(req.histologies)).all()
        hist_ids = [f.id for f in hist_filters]

    # Query cancer_term_id_mappings table
    id_records = db.query(models.CancerTermIdMapping).filter(
        models.CancerTermIdMapping.topography_id.in_(topo_ids),
        models.CancerTermIdMapping.histology_id.in_(hist_ids)
    ).all()

    # Collect all extra filter IDs to fetch metadata for
    all_extra_ids = set()
    for rec in id_records:
        if rec.extra_filter_ids and isinstance(rec.extra_filter_ids, list):
            for fid in rec.extra_filter_ids:
                all_extra_ids.add(fid)

    # Fetch full filter objects from 'filters' table
    filter_records = db.query(models.Filter).filter(models.Filter.id.in_(all_extra_ids)).all()
    filter_metadata_map = {
        f.id: {
            "id": f.id,
            "label": f.label,
            "category": f.category,
            "primaryGroup": f.primaryGroup,
            "description": f.description or ""
        } for f in filter_records
    }

    # Construct nested lookup map expected by frontend (topo -> hist -> list of full tag objects)
    nested_map = {}
    for rec in id_records:
        topo_key = rec.topography_label or rec.topography_id
        hist_key = rec.histology_label or rec.histology_id

        if topo_key not in nested_map:
            nested_map[topo_key] = {}

        hydrated_terms = [
            filter_metadata_map[fid] for fid in rec.extra_filter_ids if fid in filter_metadata_map
        ]
        nested_map[topo_key][hist_key] = hydrated_terms

    # Fallback to legacy CancerTermMapping table if no ID records found
    if not nested_map and req.topographies and req.histologies:
        legacy_records = db.query(models.CancerTermMapping).filter(
            models.CancerTermMapping.topography.in_(req.topographies),
            models.CancerTermMapping.histology.in_(req.histologies)
        ).all()
        for record in legacy_records:
            if record.topography not in nested_map:
                nested_map[record.topography] = {}
            nested_map[record.topography][record.histology] = record.associated_terms

    return nested_map


@router.post("/recommend-filters")
def recommend_dataset_filters(
    req: schemas.RecommendFiltersRequest,
    db: Session = Depends(database.get_db)
):
    """
    Scans dataset metadata (title, abstract, documentation, otherDataTypes, accessibility)
    and predicts high-confidence datasetFilters matching ICD-O topography & histology rules,
    data-type hierarchies, and access governance.
    """
    from helpers.filter_recommender import FilterRecommender
    recommender = FilterRecommender(db)

    metadata = req.metadata
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    elif not isinstance(metadata, dict):
        metadata = {}

    # If metadata has no substantive text yet, but a dataset_id is provided, try loading from the database
    eff_meta = metadata.get('metadata_blob') if isinstance(metadata.get('metadata_blob'), dict) else metadata
    target_team = eff_meta.get('team_id') or getattr(req, 'team_id', None)
    if target_team and dependencies.check_sandbox_team(db, target_team):
        return []

    has_text = bool(
        (eff_meta.get('summary') or {}).get('title') or
        (eff_meta.get('summary') or {}).get('abstract') or
        (eff_meta.get('documentation') or {}).get('description') or
        eff_meta.get('title') or
        eff_meta.get('name') or
        eff_meta.get('abstract') or
        eff_meta.get('description')
    )

    if not has_text and req.dataset_id:
        ds = None
        if isinstance(req.dataset_id, int) or str(req.dataset_id).isdigit():
            ds = db.query(models.Dataset).filter(models.Dataset.id == int(req.dataset_id)).first()
        if not ds:
            ds = db.query(models.Dataset).filter(models.Dataset.datasetid == str(req.dataset_id)).first()
        if ds:
            db_meta = ds.draft_metadata_blob or ds.metadata_blob
            if isinstance(db_meta, str):
                import json
                try:
                    db_meta = json.loads(db_meta)
                except Exception:
                    db_meta = {}
            if isinstance(db_meta, dict) and db_meta:
                metadata = db_meta

    if not isinstance(metadata, dict) or not metadata:
        return {
            "success": True,
            "count": 0,
            "suggestions": []
        }

    suggestions = recommender.scan_metadata(metadata)

    # Do not reoffer filters that have already been accepted or are active in datasetFilters
    existing_filter_ids = set()
    for existing in metadata.get('datasetFilters') or []:
        if isinstance(existing, dict) and existing.get('id'):
            existing_filter_ids.add(str(existing['id']))
        elif isinstance(existing, str):
            existing_filter_ids.add(str(existing))

    if existing_filter_ids:
        suggestions = [s for s in suggestions if str(s.get('id')) not in existing_filter_ids]

    # Separate direct suggestions (for cards) from silently derived filters (hierarchical parents & cross-ref)
    direct_suggestions = [s for s in suggestions if not s.get("isDerived")]
    silent_derived = [s for s in suggestions if s.get("isDerived")]

    return {
        "success": True,
        "count": len(direct_suggestions),
        "suggestions": direct_suggestions,
        "silentDerived": silent_derived
    }


