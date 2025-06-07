from fastapi import FastAPI
from pydantic import BaseModel

from fastapi import FastAPI
from google.cloud import storage

from .renderer import render

import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

gcs_client = storage.Client()

class RenderRequest(BaseModel):
    filename: str
    title: str
    bucket_name: str
    render_id: str


@app.post("/render-color-music")
def render_color_music(request: RenderRequest):
    """"""
    # Example processing: make it uppercase
    message = f"filename: {request.filename}, title: {request.title}, bucket_name: {request.bucket_name}, render_id: {request.render_id}"

    logging.info(message)

    filename = request.filename
    title = request.title
    bucket = gcs_client.bucket(request.bucket_name) 
    render_id = request.render_id

    # Download MEI content as string
    blob = bucket.blob(f"{render_id}/{filename}")
    mei_data = blob.download_as_text(encoding="utf-8")
    
    logging.info("Rendering ...")

    svg_html_parts = render(filename, mei_data, title, bucket, render_id)

    return {"result": svg_html_parts}