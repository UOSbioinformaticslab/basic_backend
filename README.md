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

### Filter Mapping System
The backend powers the dataset upload filter system. When users select Topography and Histology tags on the frontend, it posts to the `/datasets/extra-terms` endpoint. The backend looks up these tags in the `CancerTermMapping` table and returns associated SNOMED/TCGA mappings to inject into the dataset payload before it is saved.
