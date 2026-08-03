# main.py
from fastapi import FastAPI
from database import engine, Base
from routers import snomed_filters, publications, datasets, projects, admin, auth_router
from fastapi.middleware.cors import CORSMiddleware

from migrate_db import migrate

# Run database schema migrations if needed
migrate()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRUK Datahub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://crukdatahub-production.up.railway.app",
        "https://crukdatahub-staging.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add the new auth router for the /token endpoint
app.include_router(auth_router.router)
app.include_router(datasets.router)
app.include_router(projects.router)
app.include_router(admin.router)
app.include_router(snomed_filters.router)
app.include_router(publications.router)

@app.get("/")
def health_check():
    return {"status": "active", "system": "CRUK Datahub Backend"}