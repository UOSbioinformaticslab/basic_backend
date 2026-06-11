import sys
import os
# Maintain the path adjustment for the seeders directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from database import SessionLocal
import models


def get_first_snomed_id():
    db = SessionLocal()
    try:
        first_record = db.query(models.SnomedFilter).first()

        if first_record:
            print(f"The ID of the first SNOMED filter is: {first_record.id}")
        else:
            print("The snomed_filters table is currently empty.")

    except Exception as e:
        print(f"An error occurred while querying the database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    get_first_snomed_id()