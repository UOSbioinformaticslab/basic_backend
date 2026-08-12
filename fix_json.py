import sqlite3
import json

def fix_table(conn, table):
    cols = ['metadata_blob', 'draft_metadata_blob', 'authors', 'associated_terms']
    # publications might not have draft_metadata_blob, check schema
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    schema_cols = [c[1] for c in cursor.fetchall()]
    
    actual_cols = [c for c in cols if c in schema_cols]
    if not actual_cols:
        return
        
    rows = conn.execute(f"SELECT id, {', '.join(actual_cols)} FROM {table}").fetchall()
    
    for row in rows:
        row_id = row[0]
        updates = {}
        for i, col in enumerate(actual_cols):
            val = row[i+1]
            if val is not None and isinstance(val, str) and val.startswith('"'):
                try:
                    decoded = json.loads(val)
                    updates[col] = decoded
                except:
                    pass
        
        if updates:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [row_id]
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)

conn = sqlite3.connect('cruk_datahub.db')
for table in ['datasets', 'projects', 'publications']:
    fix_table(conn, table)
    
conn.commit()
print("Fixed double-encoded JSON in local database.")
