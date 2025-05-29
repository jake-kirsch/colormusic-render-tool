from fastapi import FastAPI, UploadFile, File, Form, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import storage
import io
import os
import uuid
from typing import List
from urllib.parse import quote
import verovio
import zipfile

from .renderer import render_color_music

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def extract_xml_from_zip(filename, session_id):
    zip_blob = bucket.blob(f"{session_id}/{filename}")

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
                    new_blob = bucket.blob(f"{session_id}/{xml_filename}")
                    new_blob.upload_from_string(file_data)
                    
                    return xml_filename
    
    raise FileNotFoundError("No .xml file found in the ZIP archive.")


def generate_svg_results_html(svg_filenames: list[str], session_id: str) -> str:
    if not svg_filenames:
        return ""

    safe_session_id = quote(session_id, safe='')

    html_parts = [
        '<div style="width: 600px; margin: 0 auto; text-align: center;">',
        f'  <a href="/download-all?session_id={safe_session_id}">',
        '    <button style="background-color: #823F98; color: #ffffff; font-size: 18px; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">Download All as ZIP</button><br><br>',
        '  </a>',
        '</div',
    ]

    html_parts.append('<div class="svg-wrapper">')
    html_parts.append('<div class="svg-document">')
    
    for svg_filename in svg_filenames:
        blob = bucket.blob(f"{session_id}/{svg_filename}")
        svg_content = blob.download_as_text(encoding="utf-8")

        html_parts.append('<div class="svg-page">')
        html_parts.append(svg_content)  # inject inline SVG content
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
bucket = gcs_client.bucket("colormusic-notation-tool-staging")


@app.get("/start-session")
def start_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@app.post("/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...), title: str = Form(...), input_format: str = Form(...), session_id: str = Form(...)):
    content = await file.read()
    filename = file.filename
    
    # Clear out existing files in GCS
    blobs = bucket.list_blobs(prefix=session_id)

    for blob in blobs:
        print(f"Deleting {blob.name}...")
        blob.delete()

    blob = bucket.blob(f"{session_id}/{filename}")
    
    # Save file to GCS
    blob.upload_from_string(content)

    if input_format == "musicxml_compressed":
        filename = extract_xml_from_zip(filename, session_id)
        print(f"GCS Extract File: {filename}")

    mei_path = ""
    if input_format in ["musicxml", "musicxml_compressed", ]:
        blob = bucket.blob(f"{session_id}/{filename}")

        # Download XML content as string
        xml_content = blob.download_as_text(encoding="utf-8")

        tk = verovio.toolkit()
        tk.loadData(xml_content)

        mei_data = tk.getMEI()

        mei_filename = f"{os.path.splitext(filename)[0]}.mei"
        blob = bucket.blob(f"{session_id}/{mei_filename}")

        # Save .mei file to GCS
        blob.upload_from_string(mei_data)
    
    elif input_format == "mei":
        mei_filename = filename
        
    svg_filenames = render_color_music(mei_filename, title, bucket, session_id)
    
    return HTMLResponse(generate_svg_results_html(svg_filenames, session_id))


@app.get("/download-all")
def download_all(session_id: str):
    blobs = bucket.list_blobs(prefix=f"{session_id}/")

    # In-memory buffer for the zip file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for blob in blobs:
            if blob.name.endswith(".svg"):
                filename = os.path.basename(blob.name)
                content = blob.download_as_bytes()
                zipf.writestr(filename, content)
            elif blob.name.endswith(".mei") and "-mod.mei" not in blob.name:
                zip_filename = os.path.basename(blob.name).split(".")[0]

    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=ColorMusic_{zip_filename}.zip"}
    )
