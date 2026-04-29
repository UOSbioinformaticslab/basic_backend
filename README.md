The files for CRUK datahub frontend require a backend. 
This will be provided by HDRUK,
but in order to expediate upload of data this is a quick and dirty 
fastapi solution 
intended to be run on the same local machine as the vite npm application 
for the frontend (which should run on local:5173)
To run use
uvicorn main:app --reload --port 8000
view swagger at http://127.0.0.1:8000/docs
