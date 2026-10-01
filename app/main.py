from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import router

app = FastAPI(
    title="ComicCraft",
    description="AI Comic Story Creator using Gemini Models",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(router)