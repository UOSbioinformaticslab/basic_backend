# fix_user_teams.py
import sys
import os
parent_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(parent_dir)

import models
from database import SessionLocal

def sync_teams():
    db = SessionLocal()
    try:
        users = db.query(models.User).all()
        for user in users:
            # If they have a primary team but their teams array is empty
            if user.team_id and len(user.teams) == 0:
                team = db.query(models.Team).filter(models.Team.id == user.team_id).first()
                if team:
                    user.teams.append(team)
                    print(f"Synced team '{team.name}' to user '{user.email}'")
        db.commit()
        print("Sync complete.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sync_teams()