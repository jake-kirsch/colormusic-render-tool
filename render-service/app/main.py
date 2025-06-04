from fastapi import FastAPI

app = FastAPI()


@app.post("/render-color-music")
def render_color_music(session_id: str):
    # Example processing: make it uppercase
    result = f"Processing session {session_id} ..."

    return {"result": result}