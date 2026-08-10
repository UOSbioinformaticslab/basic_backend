# main.py
from fastapi import FastAPI
from database import engine, Base
from routers import snomed_filters, publications, datasets, projects, admin, auth_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx
import uuid
import traceback
import os

MIDDLELAYER_URL = os.getenv("MIDDLELAYER_URL", "http://localhost:8002")

async def log_error_to_middlelayer(service_name: str, correlation_id: str, message: str, stack_trace: str):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{MIDDLELAYER_URL}/logs/error",
                json={
                    "service_name": service_name,
                    "correlation_id": correlation_id,
                    "message": message,
                    "stack_trace": stack_trace
                },
                timeout=5.0
            )
    except Exception:
        pass # Fail silently if the logger is down


from migrate_db import migrate

# Run database schema migrations if needed
migrate()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRUK Datahub")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = str(uuid.uuid4())
    message = str(exc)
    stack_trace = traceback.format_exc()

    # Fire and forget the logging task
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        log_error_to_middlelayer,
        service_name="basic_backend",
        correlation_id=correlation_id,
        message=message,
        stack_trace=stack_trace
    )

    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred.", "correlation_id": correlation_id},
        background=background_tasks
    )

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