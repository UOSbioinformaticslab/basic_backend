from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import models, schemas, database, dependencies

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("/")
def get_all_teams(db: Session = Depends(database.get_db)):
    teams = db.query(models.Team).order_by(models.Team.name).all()
    return [{"id": t.id, "name": t.name, "notification_email": t.notification_email} for t in teams]

@router.post("/{team_id}/invitations", response_model=schemas.TeamInvitationResponse)
def create_invitation(
    team_id: int,
    invitation: schemas.TeamInvitationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    # Verify current user is in the team or an admin
    if not current_user.is_admin and team_id not in [t.id for t in current_user.teams]:
        raise HTTPException(status_code=403, detail="Not authorized to invite to this team")
    
    # Check if team exists
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check if the user is already in the team
    existing_user = db.query(models.User).filter(models.User.email == invitation.email).first()
    if existing_user and team_id in [t.id for t in existing_user.teams]:
        raise HTTPException(status_code=400, detail="User is already in the team")

    # Check for pending invitation
    existing_invitation = db.query(models.TeamInvitation).filter(
        models.TeamInvitation.team_id == team_id,
        models.TeamInvitation.email == invitation.email,
        models.TeamInvitation.status == "PENDING"
    ).first()
    if existing_invitation:
        raise HTTPException(status_code=400, detail="A pending invitation already exists for this email")

    new_invitation = models.TeamInvitation(
        team_id=team_id,
        email=invitation.email,
        status="PENDING",
        is_admin=invitation.is_admin
    )
    db.add(new_invitation)
    db.commit()
    db.refresh(new_invitation)
    return new_invitation

@router.get("/invitations/pending", response_model=List[schemas.TeamInvitationResponse])
def get_pending_invitations(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    invitations = db.query(models.TeamInvitation).filter(
        models.TeamInvitation.email == current_user.email,
        models.TeamInvitation.status == "PENDING"
    ).all()
    return invitations

@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    invitation = db.query(models.TeamInvitation).filter(
        models.TeamInvitation.id == invitation_id,
        models.TeamInvitation.email == current_user.email,
        models.TeamInvitation.status == "PENDING"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or not pending")
    
    if team:
        # Add user to team if not already present
        if current_user not in team.members:
            team.members.append(current_user)
            db.commit()
            
            # If the invitation was for an admin, set the flag in the association table
            if invitation.is_admin:
                stmt = (
                    models.user_teams.update()
                    .where(
                        (models.user_teams.c.user_id == current_user.id) & 
                        (models.user_teams.c.team_id == team.id)
                    )
                    .values(is_team_admin=True)
                )
                db.execute(stmt)
    
    invitation.status = "ACCEPTED"
    db.commit()
    db.refresh(current_user)

    # Get the updated admin status for all teams
    user_team_links = db.query(models.user_teams).filter_by(user_id=current_user.id).all()
    team_admin_map = {link.team_id: link.is_team_admin for link in user_team_links}

    updated_teams = [{"id": t.id, "name": t.name, "is_team_admin": team_admin_map.get(t.id, False)} for t in current_user.teams]
    return {"status": "success", "message": "Invitation accepted", "teams": updated_teams}

@router.post("/invitations/{invitation_id}/reject")
def reject_invitation(
    invitation_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    invitation = db.query(models.TeamInvitation).filter(
        models.TeamInvitation.id == invitation_id,
        models.TeamInvitation.email == current_user.email,
        models.TeamInvitation.status == "PENDING"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or not pending")
        
    invitation.status = "REJECTED"
    db.commit()
    return {"status": "success", "message": "Invitation rejected"}

@router.get("/{team_id}/members")
def get_team_members(team_id: int, db: Session = Depends(database.get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    links = db.query(models.user_teams).filter_by(team_id=team_id).all()
    admin_map = {link.user_id: link.is_team_admin for link in links}
    
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "is_team_admin": admin_map.get(u.id, False)
        }
        for u in team.members
    ]

from pydantic import BaseModel
class AdminUpdate(BaseModel):
    is_admin: bool

@router.put("/{team_id}/members/{user_id}/admin")
def toggle_team_admin(team_id: int, user_id: int, payload: AdminUpdate, db: Session = Depends(database.get_db)):
    stmt = (
        models.user_teams.update()
        .where(
            (models.user_teams.c.user_id == user_id) & 
            (models.user_teams.c.team_id == team_id)
        )
        .values(is_team_admin=payload.is_admin)
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Member not found in team")
    db.commit()
    return {"message": "Admin status updated"}

@router.delete("/{team_id}/members/{user_id}")
def remove_team_member(team_id: int, user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not user or not team:
        raise HTTPException(status_code=404, detail="User or Team not found")
    
    if team in user.teams:
        user.teams.remove(team)
        db.commit()
    return {"message": "User removed from team"}

class NotificationEmailUpdate(BaseModel):
    notification_email: str

@router.put("/{team_id}/notification_email")
def update_notification_email(team_id: int, payload: NotificationEmailUpdate, db: Session = Depends(database.get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team.notification_email = payload.notification_email
    db.commit()
    return {"message": "Notification email updated", "notification_email": team.notification_email}

@router.get("/{team_id}/assets")
def get_team_assets(team_id: int, db: Session = Depends(database.get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    datasets = [
        {
            "id": ds.id, 
            "datasetid": ds.datasetid, 
            "title": ds.computed_title, 
            "status": ds.status
        } for ds in team.datasets if ds.active
    ]
    
    projects = [
        {
            "id": p.id,
            "pid": p.pid,
            "title": p.project_grant_name or (p.metadata_blob.get("summary", {}).get("title") if isinstance(p.metadata_blob, dict) else None) or f"Project {p.id}",
            "status": p.status
        } for p in team.projects if p.status == 'ACTIVE'
    ]
    
    publications = db.query(models.Publication).filter(models.Publication.team_id == team_id).all()
    pubs = [
        {
            "id": pub.id,
            "paper_title": pub.paper_title,
            "journal_name": pub.journal_name,
            "year_of_publication": pub.year_of_publication,
            "paper_doi": pub.paper_doi,
            "url": pub.url
        } for pub in publications
    ]

    team_tools = db.query(models.Tool).filter(models.Tool.team_id == team_id, models.Tool.status == 'ACTIVE').all()
    
    dataset_ids = [ds.id for ds in team.datasets if ds.active]
    linked_tools = []
    if dataset_ids:
        linked_tools = db.query(models.Tool).join(models.Tool.datasets).filter(
            models.Dataset.id.in_(dataset_ids),
            models.Tool.status == 'ACTIVE'
        ).all()
        
    all_tools = {t.id: t for t in (team_tools + linked_tools)}.values()

    tools = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "url": t.url
        } for t in all_tools
    ]

    return {
        "team": {
            "id": team.id, 
            "name": team.name,
            "description": team.description,
            "url": team.url,
            "notification_email": team.notification_email,
            "hdr_gateway_email": team.hdr_gateway_email
        },
        "datasets": datasets,
        "projects": projects,
        "publications": pubs,
        "tools": tools
    }

@router.get("/{team_id}")
def get_team(team_id: int, db: Session = Depends(database.get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return {
        "id": team.id,
        "name": team.name,
        "notification_email": team.notification_email,
        "hdr_gateway_email": team.hdr_gateway_email,
        "description": team.description,
        "url": team.url
    }
