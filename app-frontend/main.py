from concurrent.futures import ProcessPoolExecutor, TimeoutError
from fastapi import FastAPI, UploadFile, File, Form, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import logging
from google.cloud import storage
import io
import os
import re
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import traceback
from typing import List
from urllib.parse import quote
import unicodedata
import uuid
import zipfile

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

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

logger = logging.Client.from_service_account_json(sa_key_path).logger("colormusic-analytics-log")

def log_analytics_event(event_type, severity="INFO", **kwargs):
    """Log a structured analytics event to Cloud Logging."""
    log_entry = {
        "tag": "colormusic-analytics",
        "event_type": event_type,
        **kwargs
    }

    logger.log_struct(log_entry, severity=severity)

def gcs_friendly_filename(filename: str) -> str:
    # Normalize Unicode characters to ASCII (remove accents)
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode()

    # Replace spaces and unsafe chars with underscore
    cleaned = re.sub(r'[^A-Za-z0-9\-_.\/]', '_', only_ascii)

    # Avoid leading/trailing slashes (optional)
    cleaned = cleaned.strip('/')

    return cleaned

def verovio_job(xml):
    from verovio import toolkit
    tk = toolkit()
    tk.loadData(xml)
    return tk.getMEI()

def get_mei_safely(xml_content, timeout=10):
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(verovio_job, xml_content)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            raise RuntimeError("Verovio timed out")

@app.get("/start-render")
def start_render():
    render_id = str(uuid.uuid4())
    return {"render_id": render_id}


@app.post("/upload")
@limiter.limit(rate_limit_per_minute)
async def upload(request: Request, response: Response, file: UploadFile = File(...), title: str = Form(...), render_id: str = Form(...)):
    content = await file.read()
    filename = file.filename
    
    # TODO make the filename GCS friendly
    filename = gcs_friendly_filename(filename)

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
    
    try:
        if input_format == "musicxml_compressed":
            
            filename = extract_xml_from_zip(filename, render_id)
            print(f"GCS Extract File: {filename}")
    except:
        log_analytics_event(
            event_type="render_error", 
            severity="ERROR", 
            render_id=render_id, 
            title=title, 
            filename=filename,
            stack_trace=traceback.format_exc()
        )

        return HTMLResponse(f"<strong>Error occurred trying to extract .xml from .mxl file. Error event has been captured for render id: {render_id}.</strong>")

    try:
        if input_format in ["musicxml", "musicxml_compressed", ]:
            blob = bucket.blob(f"{render_id}/{filename}")

            # Download XML content as string
            xml_content = blob.download_as_text(encoding="utf-8")

            mei_data = get_mei_safely(xml_content)

            # tk = verovio.toolkit()
            # tk.loadData(xml_content)

            # mei_data = tk.getMEI()

            filename = f"{os.path.splitext(filename)[0]}.mei"
            blob = bucket.blob(f"{render_id}/{filename}")

            # Save .mei file to GCS
            blob.upload_from_string(mei_data)
    except:
        log_analytics_event(
            event_type="render_error", 
            severity="ERROR", 
            render_id=render_id, 
            title=title, 
            filename=filename,
            stack_trace=traceback.format_exc()
        )

        return HTMLResponse(f"<strong>Error occurred trying to convert MusicXML file to MEI.  Error event has been captured for render id: {render_id}.</strong>")

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
        return HTMLResponse(f"<strong>{response.json()['error']}</strong>")
    

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
