# routers/tools.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session, selectinload
from dependencies import get_current_user
import database, schemas, models, crud

router = APIRouter(prefix="/tools", tags=["tools"])

def check_is_team_admin(db: Session, user_id: int, team_id: int) -> bool:
    if not user_id or not team_id:
        return False
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and team_id in [t.id for t in user.teams]:
        return True
    link = db.query(models.user_teams).filter(
        models.user_teams.c.user_id == user_id,
        models.user_teams.c.team_id == team_id
    ).first()
    return link is not None


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

    if not check_is_team_admin(db, current_user.id, tool_in.team_id):
        raise HTTPException(
            status_code=403,
            detail="User must be a team admin (is_team_admin) for the active team to create tools."
        )

    return crud.create_tool(db=db, tool_in=tool_in, user_id=current_user.id)


@router.get("/", response_model=List[schemas.ToolResponse])
def read_tools(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db)
):
    return crud.get_tools(db=db, skip=skip, limit=limit)


@router.get("/{tool_id}", response_model=schemas.ToolResponse)
def read_tool(tool_id: int, db: Session = Depends(database.get_db)):
    db_tool = crud.get_tool(db=db, tool_id=tool_id)
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return db_tool


@router.delete("/{tool_id}")
def delete_tool(
    tool_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tool = crud.get_tool(db=db, tool_id=tool_id)
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if not check_is_team_admin(db, current_user.id, db_tool.team_id):
        raise HTTPException(
            status_code=403,
            detail="User must be a team admin (is_team_admin) for the active team to delete tools."
        )

    try:
        crud.delete_tool(db=db, db_tool=db_tool)
        return {"message": "Tool successfully deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete tool: {str(e)}")


@router.put("/{tool_id}", response_model=schemas.ToolResponse)
def update_tool(
    tool_id: int,
    tool_in: schemas.ToolCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tool = crud.get_tool(db=db, tool_id=tool_id)
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if not check_is_team_admin(db, current_user.id, db_tool.team_id):
        raise HTTPException(
            status_code=403,
            detail="User must be a team admin (is_team_admin) for the active team to update tools."
        )

    return crud.update_tool(db=db, db_tool=db_tool, tool_in=tool_in)

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

    if not check_is_team_admin(db, current_user.id, db_tool.team_id):
        raise HTTPException(
            status_code=403,
            detail="User must be a team admin (is_team_admin) for the active team to link tools."
        )

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
