"""
seed_extra_terms_from_results.py

Seeder script that reads /Users/skw24/CRUK/website/CRUK-taxonomies/results_dictionary.json,
maps topography & histology labels to their corresponding filter string IDs via the 'filters' table,
extracts all CRUK and TCGA extra filter IDs into a single list, and populates the
'cancer_term_id_mappings' table in cruk_datahub.db.
"""

import os
import sys
import json
import sqlite3
import time

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "cruk_datahub.db")
RESULTS_JSON_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..", "CRUK-taxonomies", "results_dictionary.json")
)


def seed_cancer_term_id_mappings():
    print("=" * 70)
    print("Seeding 'cancer_term_id_mappings' Table from results_dictionary.json")
    print("=" * 70)

    if not os.path.exists(RESULTS_JSON_PATH):
        raise FileNotFoundError(f"results_dictionary.json not found at: {RESULTS_JSON_PATH}")

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at: {DB_PATH}. Run seed_filters.py first.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Step 1: Ensure filters table exists and load label -> id lookup map
    print("\n[Step 1/4] Loading label-to-ID mapping from 'filters' table...")
    cursor.execute("SELECT label, id FROM filters")
    rows = cursor.fetchall()
    if not rows:
        raise ValueError("The 'filters' table is empty. Please run seeders/seed_filters.py first.")

    label_to_id = {row[0]: row[1] for row in rows}
    print(f"--> Loaded {len(label_to_id)} label-to-ID mappings from database.")

    # Step 2: Read results_dictionary.json
    print(f"\n[Step 2/4] Reading taxonomy mappings from: {RESULTS_JSON_PATH}...")
    t0 = time.time()
    with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as f:
        taxonomy_data = json.load(f)
    t1 = time.time()
    print(f"--> Parsed JSON in {t1 - t0:.2f} seconds. Found {len(taxonomy_data)} topography categories.")

    # Step 3: Create target database table and indexes
    print("\n[Step 3/4] Preparing 'cancer_term_id_mappings' table structure...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cancer_term_id_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topography_id TEXT,
            histology_id TEXT,
            topography_label TEXT,
            histology_label TEXT,
            extra_filter_ids JSON
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_topo_hist_id ON cancer_term_id_mappings(topography_id, histology_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_topo_id ON cancer_term_id_mappings(topography_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_hist_id ON cancer_term_id_mappings(histology_id)")

    # Clear existing entries
    cursor.execute("DELETE FROM cancer_term_id_mappings")
    conn.commit()

    # Step 4: Parse mapping combinations and build DB records
    print("\n[Step 4/4] Processing combinations and inserting into SQLite...")
    records_to_insert = []
    unmapped_topologies = set()
    unmapped_histologies = set()

    for topo_label, hist_dict in taxonomy_data.items():
        topo_id = label_to_id.get(topo_label)
        if not topo_id:
            unmapped_topologies.add(topo_label)

        for hist_label, content in hist_dict.items():
            hist_id = label_to_id.get(hist_label)
            if not hist_id:
                unmapped_histologies.add(hist_label)

            results = content.get("results", [])
            extra_ids = []

            for res in results:
                # Extract IDs from CRUK filter list
                for cruk_item in res.get("CRUK", []):
                    if isinstance(cruk_item, dict) and cruk_item.get("id"):
                        extra_ids.append(cruk_item["id"])

                # Extract IDs from TCGA filter list
                for tcga_item in res.get("TCGA", []):
                    if isinstance(tcga_item, dict) and tcga_item.get("id"):
                        extra_ids.append(tcga_item["id"])

            # Deduplicate while preserving list order
            unique_extra_ids = list(dict.fromkeys(extra_ids))

            records_to_insert.append((
                topo_id,
                hist_id,
                topo_label,
                hist_label,
                json.dumps(unique_extra_ids)
            ))

    if unmapped_topologies:
        print(f"Warning: {len(unmapped_topologies)} topography labels could not be mapped to filter IDs.")
    if unmapped_histologies:
        print(f"Warning: {len(unmapped_histologies)} histology labels could not be mapped to filter IDs.")

    # Bulk insert into SQLite
    cursor.executemany("""
        INSERT INTO cancer_term_id_mappings (
            topography_id, histology_id, topography_label, histology_label, extra_filter_ids
        ) VALUES (?, ?, ?, ?, ?)
    """, records_to_insert)

    conn.commit()
    t2 = time.time()

    # Verification
    cursor.execute("SELECT COUNT(*) FROM cancer_term_id_mappings")
    total_count = cursor.fetchone()[0]

    print(f"\n--> Successfully inserted {total_count} mapping records in {t2 - t1:.2f} seconds.")

    # Test sample lookup
    print("\n--- Sample DB Lookup Verification ---")
    cursor.execute("""
        SELECT topography_id, histology_id, topography_label, histology_label, extra_filter_ids
        FROM cancer_term_id_mappings
        LIMIT 3
    """)
    sample_rows = cursor.fetchall()
    for r in sample_rows:
        print(f"  Topography ID: '{r[0]}' ({r[2]}) | Histology ID: '{r[1]}' ({r[3]}) -> Extra IDs: {r[4]}")

    conn.close()
    print("\n" + "=" * 70)
    print("Seeding finished successfully!")
    print("=" * 70)


if __name__ == "__main__":
    seed_cancer_term_id_mappings()
