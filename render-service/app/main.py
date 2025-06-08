import traceback

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from google.cloud import logging
from google.cloud import storage

from .renderer import render

app = FastAPI()

gcs_client = storage.Client()

logger = logging.Client().logger("colormusic-analytics-log")

def log_analytics_event(event_type, severity="INFO", **kwargs):
    """Log a structured analytics event to Cloud Logging."""
    log_entry = {
        "tag": "colormusic-analytics",
        "event_type": event_type,
        **kwargs
    }

    logger.log_struct(log_entry, severity=severity)


class RenderRequest(BaseModel):
    filename: str
    title: str
    bucket_name: str
    render_id: str


@app.post("/render-color-music")
def render_color_music(request: RenderRequest):
    """Render to ColorMusic"""
    # Example processing: make it uppercase
    # message = f"filename: {request.filename}, title: {request.title}, bucket_name: {request.bucket_name}, render_id: {request.render_id}"

    # logging.info(message)

    filename = request.filename
    title = request.title
    bucket = gcs_client.bucket(request.bucket_name) 
    render_id = request.render_id
    
    try:
        # Download MEI content as string
        blob = bucket.blob(f"{render_id}/{filename}")
        mei_data = blob.download_as_text(encoding="utf-8")
        
        svg_html_parts = render(filename, mei_data, title, bucket, render_id)

        return {"result": svg_html_parts}
    except:
        log_analytics_event(
            event_type="render_error", 
            severity="ERROR", 
            render_id=render_id, 
            title=title, 
            filename=filename,
            stack_trace=traceback.format_exc()
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "result": f"Unable to process file.  Error event has been captured for render id: {render_id}."
            }
        )