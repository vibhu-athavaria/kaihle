from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Kaihle API", version="0.1.0")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})
