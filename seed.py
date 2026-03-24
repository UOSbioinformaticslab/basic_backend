# seed.py
import models
from auth import get_password_hash
from database import SessionLocal, engine, Base


def seed_data():
    # 1. Create a fresh session
    db = SessionLocal()

    try:
        print("Resetting database for many-to-many schema...")
        # Drop and recreate to handle the new association table structure
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # 2. Create Research Teams
        # These are the options the user will see in their Header dropdown
        team_imaging = models.Team(name="CRUK Imaging Group")
        team_pathology = models.Team(name="CRUK Pathology Group")
        team_genomics = models.Team(name="CRUK Genomics Hub")

        db.add_all([team_imaging, team_pathology, team_genomics])
        db.commit()  # Commit teams first to generate IDs

        # 3. Create a Single User
        # We define the user profile without a fixed team_id
        admin_user = models.User(
            email="admin@sussex.ac.uk",
            name="Principal Investigator",
            hashed_password=get_password_hash("securepassword123")
        )

        # 4. Assign the User to Multiple Teams
        # SQLAlchemy handles the 'user_teams' association table automatically via .append()
        admin_user.teams.append(team_imaging)
        admin_user.teams.append(team_pathology)

        db.add(admin_user)
        db.commit()

        print("\n--- Seeding Successful ---")
        print(f"User: {admin_user.name} ({admin_user.email})")
        print(f"Assigned Teams: {[t.name for t in admin_user.teams]}")
        print("\nTest Credentials:")
        print("Username: admin@sussex.ac.uk")
        print("Password: securepassword123")

    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()