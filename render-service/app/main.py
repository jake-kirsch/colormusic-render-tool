from fastapi import FastAPI
from pydantic import BaseModel

from fastapi import FastAPI
from google.cloud import storage
import io
import os

import verovio
import zipfile

from .renderer import render

import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

gcs_client = storage.Client()

class RenderRequest(BaseModel):
    filename: str
    input_format: str
    title: str
    bucket_name: str
    session_id: str


def extract_xml_from_zip(bucket, filename, session_id):
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


@app.post("/render-color-music")
def render_color_music(request: RenderRequest):
    """"""
    # Example processing: make it uppercase
    message = f"filename: {request.filename}, input_format: {request.input_format}, title: {request.title}, bucket_name: {request.bucket_name}, session_id: {request.session_id}"

    logging.info(message)

    filename = request.filename
    input_format = request.input_format
    title = request.title
    bucket = gcs_client.bucket(request.bucket_name) 
    session_id = request.session_id

    if input_format == "musicxml_compressed":
        filename = extract_xml_from_zip(bucket, filename, session_id)
        print(f"GCS Extract File: {filename}")

    mei_path = ""
    if input_format in ["musicxml", "musicxml_compressed", ]:
        blob = bucket.blob(f"{session_id}/{filename}")

        # Download XML content as string
        xml_content = blob.download_as_text(encoding="utf-8")

        logging.info(xml_content)

        logging.info("Initializing Toolkit ...")
        tk = verovio.toolkit()
        logging.info("Loading XML to toolkit ...")
        tk.loadData(xml_content)
        logging.info("Getting MEI ...")
        mei_data = tk.getMEI()

        mei_filename = f"{os.path.splitext(filename)[0]}.mei"
        blob = bucket.blob(f"{session_id}/{mei_filename}")

        # Save .mei file to GCS
        blob.upload_from_string(mei_data)
    
    elif input_format == "mei":
        mei_filename = filename
    
    logging.info("Rendering ...")
    svg_html_parts = render(mei_filename, title, bucket, session_id)

    return {"result": svg_html_parts}