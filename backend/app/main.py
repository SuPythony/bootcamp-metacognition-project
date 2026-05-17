"""FastAPI entrypoint. Mounts chat + persona routers and loads specialization
plugins on startup. CORS allowlist is read from ALLOWED_ORIGINS (csv)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

if load_dotenv():  # loads backend/.env (or any .env on sys.path) before routes read os.environ
    print("Loaded backend/.env")
from fastapi.middleware.cors import CORSMiddleware

from app import plugin_registry
from app.chat import router as chat_router
from app.persona import _persona_dir, router as persona_router


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    plugin_registry.load_specializations()
    # Ensure persona directory exists at startup so the first request
    # doesn't race the mkdir.
    _persona_dir()
    yield


app = FastAPI(title="Aporeka", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(persona_router)
