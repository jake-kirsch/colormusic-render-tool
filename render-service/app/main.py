from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class RenderRequest(BaseModel):
    filename: str
    input_format: str
    title: str
    bucket: str
    session_id: str

@app.post("/render-color-music")
def render_color_music(request: RenderRequest):
    # Example processing: make it uppercase
    result = f"filename: {request.filename}, input_format: {request.input_format}, title: {request.title}, bucket: {request.bucket}, session_id: {session_id}"

    return {"result": result}