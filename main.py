# main.py
from fastapi import FastAPI
from database import engine, Base
from routers import datasets, projects, admin, auth_router # Rename to avoid conflict with auth.py
from fastapi.middleware.cors import CORSMiddleware

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRUK Datahub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",], # Your React URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add the new auth router for the /token endpoint
app.include_router(auth_router.router)
app.include_router(datasets.router)
app.include_router(projects.router)
app.include_router(admin.router)

@app.get("/")
def health_check():
    return {"status": "active", "system": "CRUK Datahub Backend"}