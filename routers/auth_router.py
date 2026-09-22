# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, auth, database, schemas


router = APIRouter(tags=["authentication"])


@router.post("/register")
def register_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(database.get_db)
):
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = auth.get_password_hash(user_in.password)
    new_user = models.User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=hashed_pwd,
        applicant_organisation=user_in.applicant_organisation or "University of Sussex"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Check for pending team invitations and automatically accept them
    pending_invitations = db.query(models.TeamInvitation).filter(
        models.TeamInvitation.email == user_in.email,
        models.TeamInvitation.status == "PENDING"
    ).all()

    for invitation in pending_invitations:
        team = db.query(models.Team).filter(models.Team.id == invitation.team_id).first()
        if team and new_user not in team.members:
            team.members.append(new_user)
            db.commit()
            if invitation.is_admin:
                stmt = (
                    models.user_teams.update()
                    .where(
                        (models.user_teams.c.user_id == new_user.id) & 
                        (models.user_teams.c.team_id == team.id)
                    )
                    .values(is_team_admin=True)
                )
                db.execute(stmt)
                db.commit()
        invitation.status = "ACCEPTED"
        db.commit()

    db.refresh(new_user)
    user_team_links = db.query(models.user_teams).filter_by(user_id=new_user.id).all()
    team_admin_map = {link.team_id: link.is_team_admin for link in user_team_links}

    access_token = auth.create_access_token(
        data={"sub": new_user.email, "user_id": new_user.id}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "applicant_organisation": new_user.applicant_organisation,
            "is_admin": bool(getattr(new_user, 'is_admin', False)),
            "teams": [{"id": t.id, "name": t.name, "is_team_admin": team_admin_map.get(t.id, False)} for t in new_user.teams]
        }
    }


@router.post("/token")
def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query the association table directly to get the team roles
    user_team_links = db.query(models.user_teams).filter_by(user_id=user.id).all()
    team_admin_map = {link.team_id: link.is_team_admin for link in user_team_links}

    # Include both user and team context in the token
    access_token = auth.create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "applicant_organisation": user.applicant_organisation,
            "is_admin": bool(getattr(user, 'is_admin', False)),
            "teams": [{"id": t.id, "name": t.name, "is_team_admin": team_admin_map.get(t.id, False)} for t in user.teams]
        }
    }