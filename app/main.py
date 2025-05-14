from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
import tempfile
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...), title: str = Form(...), input_format: str = Form(...)):
    content = await file.read()
    filename = file.filename
    file_path = f"app/static/uploads/{filename}"

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
        with open(mei_path, 'w') as file:
            file.write(mei_data)
    elif input_format == "mei":
        mei_path = file_path
        
    # Render SVG(s)
    output_svg_paths = render_color_music(mei_path, title)
    relative_paths = [p.replace("app/static/", "") for p in output_svg_paths]

    # Save out the last uploaded filename
    global last_uploaded_filename
    last_uploaded_filename = os.path.splitext(filename)[0]  # No extension

    return templates.TemplateResponse("index.html", {
        "request": request,
        "svgs": relative_paths,
        "uploaded": True
    })

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