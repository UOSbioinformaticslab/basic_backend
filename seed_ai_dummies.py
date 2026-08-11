import os
import json
from database import SessionLocal
from models import Dataset, User, Team

def seed_dummies():
    dummies_dir = '/Users/skw24/CRUK/website/CRUK_datahub_landing_page/src/utils/ai_dummies'
    if not os.path.exists(dummies_dir):
        print(f"Directory {dummies_dir} does not exist.")
        return

    db = SessionLocal()
    try:
        # Get a user and a team to assign
        user = db.query(User).first()
        team = db.query(Team).first()

        if not user or not team:
            print("No users or teams found in the database. Please create them first.")
            return

        # Delete all old dummies starting with cruk-dataset- or cruk-study-
        deleted_count = db.query(Dataset).filter(
            Dataset.datasetid.like('cruk-dataset-%') | Dataset.datasetid.like('cruk-study-%')
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted_count} old dummy datasets from the database.")

        files = [f for f in sorted(os.listdir(dummies_dir)) if f.endswith('.json')]
        count = 0

        for file_name in files:
            file_path = os.path.join(dummies_dir, file_name)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            datasetid = data.get('identifier')
            
            # Create new Dataset record
            new_dataset = Dataset(
                datasetid=datasetid,
                metadata_blob=data,
                draft_metadata_blob=data,
                active=True,
                status=Dataset.STATUS_ACTIVE,
                user_id=user.id,
                team_id=team.id
            )
            db.add(new_dataset)
            count += 1

        db.commit()
        print(f"Successfully seeded {count} dummy datasets into the database.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding datasets: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_dummies()
