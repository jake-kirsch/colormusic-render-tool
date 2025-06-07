from fastapi import FastAPI, UploadFile, File, Form, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import storage
import io
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import time
from typing import List
from urllib.parse import quote
import uuid
import verovio
import zipfile

from .renderer import render_color_music

# For Cloud Run Service
import json
import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account
from google.auth import jwt


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter

retry_after = "60"
rate_limit_per_minute = "3/minute"
rate_limit_per_day = "20/day"  # TODO Apply after Locals testing

app.mount("/static", StaticFiles(directory="app-frontend/static"), name="static")
templates = Jinja2Templates(directory="app-frontend/templates")

# Custom handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTMLResponse(
        status_code=429,
        content=f"""
        <div style="width: 100%; margin: 0 auto;">
            <h2>Rate limit exceeded!</h2>
            <p>Please wait before rendering more scores.  Current allowed rate is {rate_limit_per_minute}.</p>
        </div>
        """,
        headers={"Retry-After": retry_after}
    )


def extract_xml_from_zip(filename, render_id):
    zip_blob = bucket.blob(f"{render_id}/{filename}")

    # Download zip content into memory
    zip_bytes = zip_blob.download_as_bytes()

    # Open zip from bytes buffer
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
        for file_info in zip_file.infolist():
            if file_info.is_dir():
                continue  # skip directories
            
            if '/' not in file_info.filename.rstrip('/'):
                # Read file content
                file_data = zip_file.read(file_info.filename)
                
                if file_info.filename.lower().endswith(".xml"):
                    xml_filename = f'{filename.split(".")[0]}.xml'
                    
                    # Upload extracted file back to GCS
                    new_blob = bucket.blob(f"{render_id}/{xml_filename}")
                    new_blob.upload_from_string(file_data)
                    
                    return xml_filename
    
    raise FileNotFoundError("No .xml file found in the ZIP archive.")


def generate_svg_results_html(svg_html_parts: list[str], render_id: str) -> str:
    safe_render_id = quote(render_id, safe='')

    html_parts = [
        '<div style="width: 600px; margin: 0 auto; text-align: center;">',
        f'  <a href="/download-pdf?render_id={safe_render_id}">',
        '    <button style="background-color: #823F98; color: #ffffff; font-size: 18px; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">Download Full PDF</button><br><br>',
        '  </a>',
        '</div>',
        '<br>',
        '<div style="width: 600px; margin: 0 auto; text-align: center; font-size: 1.5rem;"><strong>Preview (First Page Only)</strong></div>',
        "<br>",
    ]

    html_parts.append('<div class="svg-wrapper">')
    html_parts.append('<div class="svg-document">')
    
    for svg_html_part in svg_html_parts:
        html_parts.append('<div class="svg-page">')
        html_parts.append(svg_html_part)  # inject inline SVG content
        html_parts.append('</div>')

    html_parts.append('</div>')
    html_parts.append('</div>')

    return " ".join(html_parts)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Pages
@app.get("/pages/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("pages/about.html", {"request": request})


@app.get("/pages/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse("pages/faq.html", {"request": request})


@app.get("/pages/theory", response_class=HTMLResponse)
async def theory_page(request: Request):
    return templates.TemplateResponse("pages/theory.html", {"request": request})


@app.get("/pages/render", response_class=HTMLResponse)
async def render_page(request: Request, uploaded: bool = False, svgs: List[str] = []):
    return templates.TemplateResponse("pages/render.html", {
        "request": request,
        "uploaded": uploaded,
        "svgs": svgs,
    })


# Load the service account credentials
sa_key_path = os.getenv("COLORMUSIC_SA_KEY")
gcs_client = storage.Client.from_service_account_json(sa_key_path)
bucket = gcs_client.bucket("colormusic-notation-tool-render-staging")

CLOUD_RUN_URL = "https://colormusic-render-svc-388982170722.us-east1.run.app/render-color-music"
AUDIENCE = CLOUD_RUN_URL

# Create credentials from service account file
credentials = service_account.IDTokenCredentials.from_service_account_file(
    sa_key_path,
    target_audience=AUDIENCE
)

@app.get("/start-render")
def start_render():
    render_id = str(uuid.uuid4())
    return {"render_id": render_id}


@app.post("/upload")
@limiter.limit(rate_limit_per_minute)
async def upload(request: Request, response: Response, file: UploadFile = File(...), title: str = Form(...), render_id: str = Form(...)):
    content = await file.read()
    filename = file.filename
    
    # Determine input_format
    file_extension = os.path.splitext(filename)[1][1:].lower()

    input_format = None

    if file_extension in ["mxl"]:
        input_format = "musicxml_compressed"
    elif file_extension in ["mei"]:
        input_format = "mei"
    elif file_extension in ["musicxml", "xml"]:
        input_format = "musicxml"
    else:
        return HTMLResponse("<div>Unable to determine file type based on extension ...</div>")

    blob = bucket.blob(f"{render_id}/{filename}")
    
    # Save file to GCS
    blob.upload_from_string(content)
    
    if input_format == "musicxml_compressed":
        filename = extract_xml_from_zip(filename, render_id)
        print(f"GCS Extract File: {filename}")

    if input_format in ["musicxml", "musicxml_compressed", ]:
        blob = bucket.blob(f"{render_id}/{filename}")

        # Download XML content as string
        xml_content = blob.download_as_text(encoding="utf-8")

        tk = verovio.toolkit()
        tk.loadData(xml_content)

        mei_data = tk.getMEI()

        filename = f"{os.path.splitext(filename)[0]}.mei"
        blob = bucket.blob(f"{render_id}/{filename}")

        # Save .mei file to GCS
        blob.upload_from_string(mei_data)
    
    # Call Render Service
    credentials.refresh(GoogleRequest())

    headers = {"Authorization": f"Bearer {credentials.token}"}
    payload = {"filename": filename,
               "title": title,
               "bucket_name": bucket.name,
               "render_id": render_id, }

    response = requests.post(CLOUD_RUN_URL, json=payload, headers=headers)

    if response.ok:
        svg_html_parts = response.json()["result"]
        
        return HTMLResponse(generate_svg_results_html(svg_html_parts, render_id))
    else:
        print("Error:", response.status_code, response.text)


@app.get("/download-pdf")
def download_pdf(render_id: str):
    blobs = bucket.list_blobs(prefix=f"{render_id}/")

    for blob in blobs:
        if blob.name.endswith(".pdf"):
            # Download the blob into memory
            pdf_io = io.BytesIO()
            blob.download_to_file(pdf_io)
            pdf_io.seek(0)

            return StreamingResponse(
                pdf_io,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{blob.name.split("/")[-1]}"'
                },
            )
    
    raise HTTPException(status_code=404, detail="PDF not found in GCS!")
