from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class RenderRequest(BaseModel):
    session_id: str

@app.post("/render-color-music")
def render_color_music(request: RenderRequest):
    # Example processing: make it uppercase
    result = f"Processing session {request.session_id} ..."

    return {"result": result}