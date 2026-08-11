import sys
import pathlib
sys.path.append(pathlib.Path.parent)
from sqlalchemy.orm.attributes import flag_modified
from database import SessionLocal
import models


def migrate_authors_to_list_of_strings():
    db = SessionLocal()
    try:
        publications = db.query(models.Publication).all()
        updated_count = 0

        for pub in publications:
            if not pub.authors:
                continue

            needs_update = False
            new_authors = []

            for author in pub.authors:
                if isinstance(author, dict):
                    # Extract the string from the dictionary
                    # Adjust the key ('name') if your existing dictionaries use a different key
                    author_name = f"{author.get('family', author.get('name', ''))}, {author.get('given', '')}".strip(", ")
                    if author_name:
                        new_authors.append(author_name)
                    else:
                        # Fallback if the dictionary is structured differently
                        new_authors.append(str(author))

                    needs_update = True
                elif isinstance(author, str):
                    # Already in the correct format
                    new_authors.append(author)

            if needs_update:
                pub.authors = new_authors
                # Alert SQLAlchemy that a JSON/ARRAY column has been mutated
                flag_modified(pub, "authors")
                updated_count += 1

        db.commit()
        print(f"Migration complete. Updated {updated_count} publications.")

    except Exception as e:
        db.rollback()
        print(f"An error occurred: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # It is recommended to back up your database before running this script.
    migrate_authors_to_list_of_strings()