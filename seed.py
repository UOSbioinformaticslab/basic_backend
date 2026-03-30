# seed.py
import models
from auth import get_password_hash
from database import SessionLocal, engine, Base

def seed_data():
    db = SessionLocal()

    try:
        print("Resetting database for many-to-many schema...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # 1. Create Research Teams
        team_imaging = models.Team(name="CRUK Imaging Group")
        team_pathology = models.Team(name="CRUK Pathology Group")
        team_genomics = models.Team(name="CRUK Genomics Hub")

        db.add_all([team_imaging, team_pathology, team_genomics])
        db.commit()

        # 2. Create Users
        admin_user = models.User(
            email="admin@sussex.ac.uk",
            name="Principal Investigator",
            hashed_password=get_password_hash("securepassword123")
        )

        # Sarah Wooller
        sarah_user = models.User(
            email="me@sussex.ac.uk",
            name="Sarah Wooller",
            hashed_password=get_password_hash("securepassword123")
        )

        # 3. Assign Users to Teams
        # Principal Investigator in Imaging and Pathology
        admin_user.teams.append(team_imaging)
        admin_user.teams.append(team_pathology)

        # Sarah Wooller in all three teams
        sarah_user.teams.append(team_imaging)
        sarah_user.teams.append(team_pathology)
        sarah_user.teams.append(team_genomics)

        db.add_all([admin_user, sarah_user])
        db.commit()

        # 4. Create Projects for team_imaging
        # Project 1: Imaging of Prostatic Carcinoma
        project1 = models.Project(
            pid="PID-CRUK-001",
            version="1.0",
            projectGrantName="Imaging of Prostatic Carcinoma",
            leadResearcher="Sarah Wooller",
            leadResearchInstitute="University of Sussex",
            grantNumbers="CRUK-2026-X1",
            projectGrantStartDate="2026-01-01",
            projectGrantEndDate="2029-12-31",
            projectGrantScope="Analysis of MRI data for early detection of prostatic carcinoma.",
            metadata_blob={"internal_ref": "SUSSEX-IMG-01"},
            status="DRAFT",
            user=sarah_user,
            team=team_imaging
        )

        # Project 2: Comparative Imaging Study
        project2 = models.Project(
            pid="PID-CRUK-002",
            version="1.1",
            projectGrantName="Comparative Imaging Study",
            leadResearcher="Sarah Wooller",
            leadResearchInstitute="University of Sussex",
            grantNumbers="CRUK-2026-X2",
            projectGrantStartDate="2026-06-01",
            projectGrantEndDate="2030-05-31",
            projectGrantScope="A study comparing digital pathology and imaging modalities.",
            metadata_blob={"internal_ref": "SUSSEX-IMG-02"},
            status="DRAFT",
            user=sarah_user,
            team=team_imaging
        )

        db.add_all([project1, project2])
        db.commit()

        print("\n--- Seeding Successful ---")
        print(f"Users seeded: {admin_user.email}, {sarah_user.email}")
        print(f"Projects seeded for team '{team_imaging.name}': 2")

    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()