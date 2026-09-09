# CRUK Basic Backend

The **CRUK Basic Backend** is a FastAPI microservice running on `http://localhost:8000`. It provides the core database and API endpoints for managing Users, Teams, Datasets (JSON metadata blobs & draft states), Projects, Publications, Tools, and Team Invitations.

---

## 🚀 System Setup & Quick Start

### System Architecture Overview

The CRUK Metadata Catalogue consists of five inter-connected repositories:

1. **Frontend Landing Page** (`CRUK_datahub_landing_page`) — [`git@github.com:UOSbioinformaticslab/CRUK_datahub_landing_page.git`](https://github.com/UOSbioinformaticslab/CRUK_datahub_landing_page)
   * **Role**: React/Vite user interface running on `http://localhost:5173`. Provides dataset browsing, search, metadata upload forms, custodian management, and live schema documentation views.
2. **Basic Backend** (`basic/basic_backend`) — [`git@github.com:UOSbioinformaticslab/basic_backend.git`](https://github.com/UOSbioinformaticslab/basic_backend) — *(You are here)*
   * **Role**: Core FastAPI database backend running on `http://localhost:8000`. Manages Users, Teams, Datasets (JSON metadata blobs & draft states), Projects, Publications, Tools, and Team Invitations.
3. **Middle Layer Proxy** (`middle`) — [`git@github.com:UOSbioinformaticslab/cruk-middle-layer.git`](https://github.com/UOSbioinformaticslab/cruk-middle-layer)
   * **Role**: Administrative FastAPI service running on `http://localhost:8002`. Manages new Data Custodian team request applications (`TeamRequest`) and centralized system error logging (`ErrorLog`).
4. **CRUK Semantic Schema Viewer & Package** (`semantic-schema/cruk-semantic-schema`) — [`git@github.com:UOSbioinformaticslab/cruk-semantic-schema.git`](https://github.com/UOSbioinformaticslab/cruk-semantic-schema)
   * **Role**: React component library & standalone interactive UI for rendering the CRUK 1.0.0 semantic schema overlay dynamically fetched from HDRUK schemata.
5. **AI Microservices** (`ai/ai-microservices`) — *Optional / Private Repository* — [`git@github.com:UOSbioinformaticslab/ai-microservices.git`](https://github.com/UOSbioinformaticslab/ai-microservices)
   * **Role**: FastAPI AI microservice running on `http://localhost:8001`. Powered by Google Gemini API for intelligent metadata extraction, automated tagging, and semantic search assistance. Note: This repository is private. If you do not have access to it or do not have a Gemini API key, the rest of the CRUK catalogue will run fully and seamlessly without it.

---

### Environment Setup (`.env` Configuration)

Before running this backend microservice, a `.env` file must be created in this folder:

1. **Automatic Setup**:
   Running `./start_all.sh` from the workspace root or `CRUK_datahub_landing_page/` will automatically copy `.env.example` to `.env` if no `.env` file is present.
2. **Manual Setup**:
   You can manually copy the provided template file:
   ```bash
   cp .env.example .env
   ```
3. **Variable Breakdown**:
   * `DATABASE_URL`: Connection string for the database (defaults to local SQLite `sqlite:///./cruk_datahub.db`).
   * `DATABASE_PUBLIC_URL`: Base URL where the backend is hosted (defaults to `http://localhost:8000`).
   * `SECRET_KEY`: Secret key used for signing JWT authentication tokens. Replace with a secure random string in production.
   * `ALGORITHM`: JWT signing algorithm (defaults to `HS256`).
   * `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token lifetime in minutes (defaults to `600`).
   * `ADMIN_PASSWORD`: Default admin user password for seeding initial admin accounts (`seed_sarah.py`).

Example `.env` configuration:

```env
DATABASE_URL="sqlite:///./cruk_datahub.db"
DATABASE_PUBLIC_URL="http://localhost:8000"
SECRET_KEY="your-secure-random-secret-key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=600
ADMIN_PASSWORD="your-admin-password"
```

---

### Quick Start & Execution

To launch this service individually:

```bash
uvicorn main:app --reload --port 8000
```

To start the entire system together:

```bash
# From workspace root or CRUK_datahub_landing_page
./start_all.sh
```

View interactive OpenAPI documentation at: `http://localhost:8000/docs`

---

## 🗄 Database Initialization & Models

The SQLite database file (`cruk_datahub.db`) is automatically initialized if it does not exist when starting the backend.

### Filter Mapping System
The backend powers the dataset upload filter system. When users select Topography and Histology tags on the frontend, it posts to the `/datasets/extra-terms` endpoint. The backend looks up these tags in the `CancerTermMapping` table and returns associated SNOMED/TCGA mappings to inject into the dataset payload.

### Data Custodians & Asset Management
The backend provides comprehensive support for Data Custodians (teams) and their actions:
- **Public Team Assets**: The `/teams/{team_id}/assets` endpoint aggregates and returns all active datasets, projects, and publications associated with a specific team.
- **Asset Management**: Endpoints like `/datasets/list/simple` filter results based on the logged-in user's active team, allowing editors to manage both active records and drafts securely.
