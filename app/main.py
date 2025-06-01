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


from playwright.sync_api import sync_playwright


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter

retry_after = "60"
rate_limit = "3/minute"

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Custom handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTMLResponse(
        status_code=429,
        content=f"""
        <div style="width: 100%; margin: 0 auto;">
            <h2>Rate limit exceeded!</h2>
            <p>Please wait before rendering more scores.  Current allowed rate is {rate_limit}.</p>
        </div>
        """,
        headers={"Retry-After": retry_after}
    )


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
        f'  <a href="/download-pdf?session_id={safe_session_id}">',
        '    <button style="background-color: #823F98; color: #ffffff; font-size: 18px; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">Download PDF</button><br><br>',
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


def generate_svg_results_html2(svg_html_parts: list[str], session_id: str) -> str:
    safe_session_id = quote(session_id, safe='')

    html_parts = [
        '<div style="width: 600px; margin: 0 auto; text-align: center;">',
        f'  <a href="/download-pdf?session_id={safe_session_id}">',
        '    <button style="background-color: #823F98; color: #ffffff; font-size: 18px; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">Download PDF</button><br><br>',
        '  </a>',
        '</div',
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


@app.get("/start-session")
def start_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@app.post("/upload")
@limiter.limit(rate_limit)
async def upload(request: Request, response: Response, file: UploadFile = File(...), title: str = Form(...), input_format: str = Form(...), session_id: str = Form(...)):
    start_time = time.time()
    
    content = await file.read()
    filename = file.filename
    
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
        
    # svg_filenames = await render_color_music(mei_filename, title, bucket, session_id)
    svg_html_parts = await render_color_music(mei_filename, title, bucket, session_id)
    
    end_time = time.time()

    elapsed = end_time - start_time

    # Having rendering take at least 5 seconds for effect
    if elapsed < 5:
        time.sleep(5 - elapsed)

    # return HTMLResponse(generate_svg_results_html(svg_filenames, session_id))
    return HTMLResponse(generate_svg_results_html2(svg_html_parts, session_id))


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

@app.get("/download-pdf")
def download_pdf(session_id: str):
    blobs = bucket.list_blobs(prefix=f"{session_id}/")

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

# # Lots of limitations with svglib/reportlab
# from svglib.svglib import svg2rlg
# from reportlab.graphics import renderPDF
# from reportlab.pdfgen import canvas

# @app.get("/download-pdf")
# def download_pdf(session_id: str):
#     # List SVG blobs by prefix (session_id folder)
#     blobs = list(bucket.list_blobs(prefix=f"{session_id}/"))
#     svg_blobs = [b for b in blobs if b.name.endswith(".svg")]

#     if not svg_blobs:
#         return Response("No SVG files found", status_code=404)

#     # Prepare PDF buffer
#     pdf_buffer = io.BytesIO()
#     page_size = (595, 842)  # A4 in points (width, height)
#     c = canvas.Canvas(pdf_buffer, pagesize=page_size)
#     width, height = page_size

#     for blob in blobs:
#         if blob.name.endswith("colormusic.svg"):
#             # Download SVG into memory
#             svg_bytes = blob.download_as_bytes()
#             svg_str = svg_bytes.decode("utf-8")

#             # Convert SVG string bytes to ReportLab drawing
#             drawing = svg2rlg(io.BytesIO(svg_bytes))

#             # Calculate scale to fit page, keep aspect ratio
#             scale_x = width / drawing.width
#             scale_y = height / drawing.height
#             scale = min(scale_x, scale_y)

#             # Center the SVG on the page
#             x = (width - drawing.width * scale) / 2
#             y = (height - drawing.height * scale) / 2

#             drawing.scale(scale, scale)
#             renderPDF.draw(drawing, c, x, y)
#             c.showPage()  # Next page
#         elif blob.name.endswith(".mei") and "-mod.mei" not in blob.name:
#             pdf_filename = os.path.basename(blob.name).split(".")[0]

#     c.save()
#     pdf_buffer.seek(0)

#     headers = {
#         "Content-Disposition": f"inline; filename={pdf_filename}.pdf"
#     }

#     return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)

# Cairo is cutting off top half of the noteheads
# import cairosvg

# @app.get("/download-pdf")
# def download_pdf(session_id: str):
#     blobs = bucket.list_blobs(prefix=f"{session_id}/")

#     pdf_filename = None
    
#     for blob in blobs:
#         if blob.name.endswith("colormusic.svg"):
#             # Download SVG into memory
#             svg_bytes = blob.download_as_bytes()

#             # Convert SVG to PDF in memory
#             pdf_io = io.BytesIO()
#             cairosvg.svg2pdf(bytestring=svg_bytes, write_to=pdf_io)

#             # Rewind and return as streaming response
#             pdf_io.seek(0)
#         elif blob.name.endswith(".mei") and "-mod.mei" not in blob.name:
#             pdf_filename = os.path.basename(blob.name).split(".")[0]

    
#     return StreamingResponse(
#         content=pdf_io,
#         media_type="application/pdf",
#         headers={ "Content-Disposition": f"inline; filename=ColorMusic_{pdf_filename}.pdf" }
#         # headers={ "Content-Disposition": f"attachment; filename=ColorMusic_{pdf_filename}.pdf" }
#     )

# # This Works, moving this action to the renderer.py
# @app.get("/download-pdf")
# def download_pdf(session_id: str):
#     blobs = bucket.list_blobs(prefix=f"{session_id}/")

#     pdf_filename = None
    
#     svg_html_parts = []
#     for blob in blobs:
#         if blob.name.endswith("colormusic.svg"):
#             # Download SVG into memory
#             svg_bytes = blob.download_as_bytes()
#             svg = svg_bytes.decode("utf-8")
#             svg_html_parts.append(f"<div style='page-break-after: always'>{svg}</div>")
#         elif blob.name.endswith(".mei") and "-mod.mei" not in blob.name:
#             pdf_filename = os.path.basename(blob.name).split(".")[0]

#     html_content = f"""
#     <html>
#       <head>
#         <style>
#           @page {{ size: Letter; margin: 0 }}
#           body {{ margin: 0 }}
#         </style>
#       </head>
#       <body>
#         {''.join(svg_html_parts)}
#       </body>
#     </html>
#     """

#     pdf_io = io.BytesIO()

#     with sync_playwright() as p:
#         browser = p.chromium.launch()
#         page = browser.new_page()
#         page.set_content(html_content, wait_until="load")
#         pdf_bytes = page.pdf(format="Letter", print_background=True)
#         browser.close()

#     pdf_io.write(pdf_bytes)
#     pdf_io.seek(0)

#     return StreamingResponse(
#         pdf_io,
#         media_type="application/pdf",
#         headers={"Content-Disposition": f"inline; filename={pdf_filename}.pdf"}
#     )