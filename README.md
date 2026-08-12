The files for CRUK datahub frontend require a backend. 
This will be provided by HDRUK,
but in order to expediate upload of data this is a quick and dirty 
fastapi solution 
intended to be run on the same local machine as the vite npm application 
for the frontend (which should run on local:5173)
To run use:
```bash
uvicorn main:app --reload --port 8000
```
View swagger at http://127.0.0.1:8000/docs

### Environment Variables
Before running the backend, you must create a `.env` file in this folder. It should contain the following configurations (you can change the values as needed):

```env
DATABASE_URL="sqlite:///./cruk_datahub.db"
DATABASE_PUBLIC_URL=""
SECRET_KEY=""
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=600
SWOOLLER_PASSWORD="your-secure-password"
```

### Database Initialization
The SQLite database file (`cruk_datahub.db`) is intentionally excluded from version control (GitHub) to prevent file size issues. You do not need to download the database file—when you start the backend, it will automatically generate a fresh `cruk_datahub.db` file and create all the necessary tables for you.

### Filter Mapping System
The backend powers the dataset upload filter system. When users select Topography and Histology tags on the frontend, it posts to the `/datasets/extra-terms` endpoint. The backend looks up these tags in the `CancerTermMapping` table and returns associated SNOMED/TCGA mappings to inject into the dataset payload before it is saved.

### Data Custodians

The backend provides comprehensive support for Data Custodians (teams) and their actions:
- **Public Team Assets**: The `/teams/{team_id}/assets` endpoint aggregates and returns all active datasets, projects, and publications associated with a specific team for the public Data Custodian page.
- **Data Custodian Actions**: The API supports team-specific actions including:
  - **Asset Management**: Endpoints like `/datasets/list/simple` automatically filter results based on the logged-in user's active team, allowing editors to manage both active records and drafts securely.
  - **Team Administration**: Endpoints to manage team invitations, toggle admin roles, and retrieve data access enquiries for the team.
