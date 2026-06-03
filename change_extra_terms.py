import os
import sys

# Maintain the path adjustment for the seeders directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

import argparse
import json
import models
from database import SessionLocal, engine, Base


def parse_extra_terms(path):
    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    mappings = []
    for topo_label, histology_dict in raw_data.items():
        for histo_label, terms_list in histology_dict.items():
            mapping_record = models.CancerTermMapping(
                topography=topo_label,
                histology=histo_label,
                associated_terms=terms_list
            )
            mappings.append(mapping_record)
    return mappings


def main():
    parser = argparse.ArgumentParser(
        prog='refresh extra terms',
        description='Deletes old cancer term mappings and seeds the database with new ones',
    )
    parser.add_argument('path', help='Path to the extra_terms.json file')
    args = parser.parse_args()

    # Issue the creation command to build the table if it does not exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Reading file and processing new mapping elements...")
        records = parse_extra_terms(args.path)

        # 1. Safely target and delete ONLY the records in the CancerTermMapping table
        print("Removing existing CancerTermMapping records...")
        deleted_count = db.query(models.CancerTermMapping).delete()
        print(f"Cleared {deleted_count} old records.")

        # 2. Stage the new records
        print(f"Staging {len(records)} new relational entries...")
        db.add_all(records)

        # 3. Commit the deletion and the additions together as one safe transaction
        db.commit()
        print("Database synchronization finished.")

    except Exception as error:
        # If anything fails, rollback prevents the deletion from becoming permanent
        db.rollback()
        print(f"Seeding aborted due to an error: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    main()