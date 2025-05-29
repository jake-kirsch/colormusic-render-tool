from fastapi import FastAPI, UploadFile, File, Form, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import storage
import io
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from typing import List
from urllib.parse import quote
import verovio
import zipfile

from .renderer import render_color_music, render_color_music2

last_uploaded_filename = ""

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
        # '<div style="width: 100%; margin: 0 auto;">',
        # '  <h2>Rendered SVGs:</h2>'
    ]

    html_parts.append('<div class="svg-wrapper">')
    html_parts.append('<div class="svg-document">')
    # for svg in svgs:
    #     svg_filename = os.path.basename(svg)
    #     html_parts.append(f'<div class="svg-page"><object data="/static/rendered_svgs/{svg_filename}" type="image/svg+xml"></object></div>')
    #     # html_parts.append('  <div>')
    #     # html_parts.append(f'    <img src="/static/rendered_svgs/{svg_filename}" alt="SVG Output" style="max-width: 100%;">')
    #     # html_parts.append('  </div>')
    
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


@app.get("/setcookie")
async def setcookie(response: Response):
    response.set_cookie(key="session_id", value="12345", httponly=True)
    return {"message": "Cookie set"}


@app.post("/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...), title: str = Form(...), input_format: str = Form(...), session_id: str = Form(...)):
    content = await file.read()
    filename = file.filename
    UPLOAD_DIR = "app/static/uploads"
    file_path = f"{UPLOAD_DIR}/{filename}"
    
    # Clear out existing files in storage
    blobs = bucket.list_blobs(prefix=session_id)

    for blob in blobs:
        print(f"Deleting {blob.name}...")
        blob.delete()

    # Switch this to google-cloud-storage
    blob = bucket.blob(f"{session_id}/{filename}")

    blob.upload_from_string(content)

    # Clear out existing files in Uploads dir
    if os.path.isdir(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))

    # Save uploaded file
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    
    if input_format == "musicxml_compressed":
        # file = extract_xml_from_zip(file_path, session_id)
        filename = extract_xml_from_zip(filename, session_id)
        print(f"GCS Extract File: {filename}")

    mei_path = ""
    if input_format in ["musicxml", "musicxml_compressed", ]:
        blob = bucket.blob(f"{session_id}/{filename}")

        # Download XML content as string
        xml_content = blob.download_as_text(encoding="utf-8")

        tk = verovio.toolkit()
        tk.loadData(xml_content)

        # tk.loadFile(file_path)

        mei_data = tk.getMEI()

        mei_path = f"app/static/uploads/{os.path.splitext(filename)[0]}.mei"
        
        # Save the MEI data to a file
        with open(mei_path, 'w', encoding='utf-8') as file:
            file.write(mei_data)

        mei_filename = f"{os.path.splitext(filename)[0]}.mei"
        blob = bucket.blob(f"{session_id}/{mei_filename}")

        blob.upload_from_string(mei_data)
    
    elif input_format == "mei":
        mei_path = file_path
        mei_filename = filename
        
    output_svg_paths = render_color_music(mei_path, title, bucket, session_id)
    svg_filenames = render_color_music2(mei_filename, title, bucket, session_id)
    relative_paths = [p.replace("app/static/", "") for p in output_svg_paths]

    # Save out the last uploaded filename
    global last_uploaded_filename
    last_uploaded_filename = os.path.splitext(filename)[0]  # No extension

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
