from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import tempfile
import zipfile

from .renderer import render_color_music

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    mei_path = f"app/static/uploads/{filename}"

    # Save uploaded MEI file
    os.makedirs(os.path.dirname(mei_path), exist_ok=True)
    with open(mei_path, "wb") as f:
        f.write(content)

    # Render SVG(s)
    output_svg_paths = render_color_music(mei_path)
    relative_paths = [p.replace("app/static/", "") for p in output_svg_paths]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "svgs": relative_paths,
        "uploaded": True
    })

@app.get("/download-all")
def download_all():
    svg_dir = "app/static/rendered_svgs"
    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(svg_dir):
            for file in files:
                if file.endswith(".svg"):
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, svg_dir)
                    zipf.write(full_path, arcname=arcname)

    return FileResponse(zip_path, media_type="application/zip", filename="ColorMusic_SVGs.zip")