import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm, scraper, sheets

app = FastAPI(title="Job App Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobLinkRequest(BaseModel):
    link: str
    password: str


@app.post("/api/log-job")
def log_job(req: JobLinkRequest):
    expected_password = os.environ.get("APP_PASSWORD")
    if expected_password and req.password != expected_password:
        raise HTTPException(status_code=401, detail="Incorrect password.")

    if not req.link.strip().lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Please provide a valid URL.")

    try:
        page = scraper.fetch_job_page(req.link)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't fetch that link: {e}")

    try:
        fields = llm.extract_job_fields(page["title"], page["text"], page["json_ld"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't parse the listing: {e}")

    try:
        row = sheets.add_application(
            company=fields["company"],
            position=fields["position"],
            location=fields["location"],
            pay=fields["pay"],
            link=req.link,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't write to Google Sheets: {e}")

    return {"ok": True, "row": row}


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the frontend (static/index.html) at the root.
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")
