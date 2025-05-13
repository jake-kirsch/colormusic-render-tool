from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from app.renderer import render_color_music

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
