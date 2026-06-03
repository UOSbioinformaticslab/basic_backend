import os
import sys

# Maintain the path adjustment for the seeders directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

import argparse
import json
import models
from database import SessionLocal, engine, Base  # Ensure engine and Base are imported


def seed_extra_terms(path):
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
        prog='seed extra terms',
        description='Parses a hierarchical cancer ontology JSON file and seeds the mapping database',
    )
    parser.add_argument('path', help='Path to the extra_terms.json file')
    args = parser.parse_args()

    # Issue the creation command to build the table if it does not exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Reading file and processing mapping elements...")
        records = seed_extra_terms(args.path)

        print(f"Writing {len(records)} relational entries to the database...")
        db.add_all(records)
        db.commit()
        print("Database synchronization finished.")

    except Exception as error:
        db.rollback()
        print(f"Seeding aborted due to an error: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    main()