from database import engine
from models import Publication, PublicationHasDataset, PublicationHasProject

# Drop the specific tables
PublicationHasDataset.__table__.drop(engine, checkfirst=True)
PublicationHasProject.__table__.drop(engine, checkfirst=True)
Publication.__table__.drop(engine, checkfirst=True)

print("Tables dropped successfully.")