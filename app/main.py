from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path
import shutil
import tempfile
from typing import List
import verovio
import zipfile

from .renderer import render_color_music

last_uploaded_filename = ""

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def extract_xml_from_zip(zip_path, extract_dir="app/static/extract/"):
    # Remove existing extract directory
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # Search for .xml file in the extracted directory
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith(".xml"):
                return os.path.join(root, file)
    
    raise FileNotFoundError("No .xml file found in the ZIP archive.")

def generate_svg_results_html(svgs: list[str]) -> str:
    # static/rendered_svgs/BareNecessities-1-colormusic.svg

    if not svgs:
        return ""

    html_parts = [
        '<div style="width: 600px; margin: 0 auto;">',
        '  <a href="/download-all">',
        '    <button>Download All as ZIP</button><br><br>',
        '  </a>',
        '</div',
        # '<div style="width: 100%; margin: 0 auto;">',
        # '  <h2>Rendered SVGs:</h2>'
    ]

    html_parts.append('<div class="svg-document">')
    for svg in svgs:
        svg_filename = os.path.basename(svg)
        html_parts.append(f'<div class="svg-page"><object data="/static/rendered_svgs/{svg_filename}" type="image/svg+xml"></object></div>')
        # html_parts.append('  <div>')
        # html_parts.append(f'    <img src="/static/rendered_svgs/{svg_filename}" alt="SVG Output" style="max-width: 100%;">')
        # html_parts.append('  </div>')

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

@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...), title: str = Form(...), input_format: str = Form(...)):
    content = await file.read()
    filename = file.filename
    UPLOAD_DIR = "app/static/uploads"
    file_path = f"{UPLOAD_DIR}/{filename}"

    # Clear out existing files in Uploads dir
    if os.path.isdir(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))

    # Save uploaded file
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    
    if input_format == "musicxml_compressed":
        file_path = extract_xml_from_zip(file_path)

    mei_path = ""
    if input_format in ["musicxml", "musicxml_compressed", ]:
        tk = verovio.toolkit()

        tk.loadFile(file_path)

        mei_data = tk.getMEI()

        mei_path = f"app/static/uploads/{os.path.splitext(filename)[0]}.mei"
        
        # Save the MEI data to a file
        with open(mei_path, 'w', encoding='utf-8') as file:
            file.write(mei_data)
    
    elif input_format == "mei":
        mei_path = file_path
        
    # Render SVG(s)
    output_svg_paths = render_color_music(mei_path, title)
    relative_paths = [p.replace("app/static/", "") for p in output_svg_paths]

    # Save out the last uploaded filename
    global last_uploaded_filename
    last_uploaded_filename = os.path.splitext(filename)[0]  # No extension

    return HTMLResponse(generate_svg_results_html(relative_paths))

@app.get("/download-all")
def download_all():
    global last_uploaded_filename

    svg_dir = "app/static/rendered_svgs"
    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(svg_dir):
            for file in files:
                if file.endswith(".svg"):
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, svg_dir)
                    zipf.write(full_path, arcname=arcname)

    return FileResponse(zip_path, media_type="application/zip", filename=f"ColorMusic_{last_uploaded_filename}.zip")