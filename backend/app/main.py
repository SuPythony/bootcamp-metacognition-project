"""FastAPI entrypoint. Mounts routers and loads specialization plugins on startup."""

from fastapi import FastAPI

# Routers (stubs — see chat.py, persona.py)
# from app.chat import router as chat_router
# from app.persona import router as persona_router
# from app.plugin_registry import load_specializations, get_specializations

app = FastAPI(title="Socratic Tutor")


@app.on_event("startup")
def _startup() -> None:
    # load_specializations()
    pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# app.include_router(chat_router)
# app.include_router(persona_router)


# @app.get("/specializations")
# def list_specializations():
#     return get_specializations()
