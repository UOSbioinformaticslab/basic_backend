# routers/tools.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from dependencies import get_current_user
import database, schemas, models

router = APIRouter(prefix="/tools", tags=["tools"])

@router.post("/", response_model=schemas.ToolResponse)
def create_tool(
    tool_in: schemas.ToolCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if tool_in.team_id is None:
        raise HTTPException(
            status_code=400,
            detail="No active team selected. Please select a team before saving."
        )

    user_team_ids = [team.id for team in current_user.teams]
    if tool_in.team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the specified team")

    # Compatibility with older Pydantic
    dumped = tool_in.dict(exclude_unset=True) if hasattr(tool_in, 'dict') else tool_in.model_dump(exclude_unset=True)
    
    linked_datasets = dumped.pop('linked_datasets', [])
    linked_projects = dumped.pop('linked_projects', [])
    
    db_tool = models.Tool(
        **dumped,
        user_id=current_user.id
    )
    db.add(db_tool)
    db.flush()  # To get the db_tool.id
    
    for ds_id in linked_datasets:
        db.add(models.ToolHasDataset(tool_id=db_tool.id, dataset_id=ds_id))
        
    for proj_id in linked_projects:
        db.add(models.ToolHasProject(tool_id=db_tool.id, project_id=proj_id))
        
    db.commit()
    db.refresh(db_tool)
    return db_tool

@router.get("/", response_model=List[schemas.ToolResponse])
def read_tools(db: Session = Depends(database.get_db)):
    return db.query(models.Tool).all()

@router.get("/{tool_id}", response_model=schemas.ToolResponse)
def read_tool(tool_id: int, db: Session = Depends(database.get_db)):
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return db_tool

@router.put("/{tool_id}", response_model=schemas.ToolResponse)
def update_tool(
    tool_id: int,
    tool_in: schemas.ToolCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    user_team_ids = [team.id for team in current_user.teams]
    if db_tool.team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the tool's team")

    dumped = tool_in.dict(exclude_unset=True) if hasattr(tool_in, 'dict') else tool_in.model_dump(exclude_unset=True)
    
    linked_datasets = dumped.pop('linked_datasets', None)
    linked_projects = dumped.pop('linked_projects', None)
    
    for key, value in dumped.items():
        setattr(db_tool, key, value)
        
    if linked_datasets is not None:
        db.query(models.ToolHasDataset).filter(models.ToolHasDataset.tool_id == tool_id).delete()
        for ds_id in linked_datasets:
            db.add(models.ToolHasDataset(tool_id=tool_id, dataset_id=ds_id))
            
    if linked_projects is not None:
        db.query(models.ToolHasProject).filter(models.ToolHasProject.tool_id == tool_id).delete()
        for proj_id in linked_projects:
            db.add(models.ToolHasProject(tool_id=tool_id, project_id=proj_id))
    
    db.commit()
    db.refresh(db_tool)
    return db_tool

@router.post("/{tool_id}/link/{entity_type}/{entity_id}")
def link_tool(
    tool_id: int,
    entity_type: str,
    entity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
        
    user_team_ids = [team.id for team in current_user.teams]
    if db_tool.team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="User is not a member of the tool's team")

    if entity_type == 'dataset':
        link = models.ToolHasDataset(tool_id=tool_id, dataset_id=entity_id)
        db.add(link)
    elif entity_type == 'project':
        link = models.ToolHasProject(tool_id=tool_id, project_id=entity_id)
        db.add(link)
    elif entity_type == 'publication':
        link = models.PublicationHasTool(tool_id=tool_id, publication_id=entity_id)
        db.add(link)
    else:
        raise HTTPException(status_code=400, detail="Invalid entity type")
        
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Link may already exist")
        
    return {"status": "success"}
