import sqlite3
import os


def append_reassigning_ids(source_db_path, dest_db_path):
    if not os.path.exists(source_db_path):
        print(f"Error: Source database '{source_db_path}' not found.")
        return
    if not os.path.exists(dest_db_path):
        print(f"Error: Destination database '{dest_db_path}' not found.")
        return

    conn = sqlite3.connect(dest_db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(f"ATTACH DATABASE '{source_db_path}' AS db_a")

        cursor.execute("SELECT name FROM db_a.sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']

        for table in tables:
            cursor.execute(f"SELECT sql FROM db_a.sqlite_master WHERE type='table' AND name='{table}';")
            create_table_sql = cursor.fetchone()[0]

            modified_create_sql = create_table_sql.replace(
                f"CREATE TABLE {table}",
                f"CREATE TABLE IF NOT EXISTS main.{table}"
            )
            cursor.execute(modified_create_sql)

            # Retrieve table schema to separate the Primary Key from standard columns
            cursor.execute(f"PRAGMA main.table_info({table})")
            columns_info = cursor.fetchall()

            # PRAGMA table_info returns tuples where index 5 indicates if the column is a PK (1 for true, 0 for false)
            non_pk_columns = [col[1] for col in columns_info if col[5] == 0]

            if not non_pk_columns:
                print(f"Skipping {table}: No standard columns available to insert.")
                continue

            cols_str = ", ".join(non_pk_columns)

            print(f"Appending records and generating new IDs for table: {table}")
            # Insert only the non-PK columns so SQLite generates new sequential PKs automatically
            cursor.execute(f"INSERT INTO main.{table} ({cols_str}) SELECT {cols_str} FROM db_a.{table}")

        conn.commit()
        print("Database merge completed with reassigned IDs.")

    except sqlite3.Error as error:
        conn.rollback()
        print(f"Database operation failed: {error}")
    finally:
        conn.close()


if __name__ == "__main__":
    append_reassigning_ids("extra.db", "cruk_datahub.db")