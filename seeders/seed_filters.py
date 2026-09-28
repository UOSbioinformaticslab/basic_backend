"""
seed_filters.py

Populates the 'filters' database table from
/Users/skw24/CRUK/website/CRUK_datahub_landing_page/src/utils/flattened_filter_data.js
"""

import os
import sys
import json
import sqlite3

# Define relative/absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "..",
        "..",
        "CRUK_datahub_landing_page",
        "src",
        "utils",
        "flattened_filter_data.js"
    )
)
DB_PATH = os.path.join(BASE_DIR, "cruk_datahub.db")


def load_filter_data_from_js(filepath):
    """
    Parses the ES module exported in flattened_filter_data.js.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Filter data file not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip ES module prefix 'export const flattenedFilterData = ' and trailing ';'
    cleaned = content.replace("export const flattenedFilterData = ", "").rstrip().rstrip(";")
    filter_data = json.loads(cleaned)
    return filter_data


def populate_filters_table():
    """
    Creates and seeds the 'filters' table in cruk_datahub.db.
    """
    print(f"Reading flattened filter data from: {JS_PATH}")
    filter_dict = load_filter_data_from_js(JS_PATH)
    print(f"Parsed {len(filter_dict)} filter records.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create the 'filters' table with string IDs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            id TEXT PRIMARY KEY,
            label TEXT,
            category TEXT,
            primaryGroup TEXT,
            description TEXT,
            parentId TEXT,
            path JSON
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_filters_label ON filters(label)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_filters_category ON filters(category)")

    # Clear existing entries for a clean seed
    cursor.execute("DELETE FROM filters")

    # Insert records
    records_to_insert = []
    for filter_id, item in filter_dict.items():
        records_to_insert.append((
            str(item.get("id")),
            item.get("label", ""),
            item.get("category", ""),
            item.get("primaryGroup", ""),
            item.get("description", ""),
            item.get("parentId") if item.get("parentId") is not None else None,
            json.dumps(item.get("path", []))
        ))

    cursor.executemany("""
        INSERT INTO filters (id, label, category, primaryGroup, description, parentId, path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records_to_insert)

    conn.commit()

    # Verify count
    cursor.execute("SELECT COUNT(*) FROM filters")
    count = cursor.fetchone()[0]
    print(f"Successfully populated 'filters' table in {DB_PATH} with {count} records.")

    # Show a sample row
    cursor.execute("SELECT id, label, category, primaryGroup, parentId, path FROM filters LIMIT 3")
    sample = cursor.fetchall()
    print("\nSample Filter Table Entries:")
    for row in sample:
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    populate_filters_table()
