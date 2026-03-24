from database import engine, Base
import models # Ensure your models are imported so Base knows them

# This creates the physical tables in your .db file
Base.metadata.create_all(bind=engine)
print("Database tables created successfully")