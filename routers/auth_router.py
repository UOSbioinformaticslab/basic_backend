# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, auth, database

router = APIRouter(tags=["authentication"])


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