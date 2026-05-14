"""POST /chat and POST /session/new handlers.

Both endpoints validate agent output (phase transitions, hint-level escalation)
per the decisions section of CLAUDE.md. /session/new runs domain classification
internally using LLM_MODEL_CLASSIFIER, then produces the tutor's opening message
using LLM_MODEL_TUTOR — single round-trip from the frontend.
"""

from fastapi import APIRouter

router = APIRouter()


# @router.post("/session/new")
# async def session_new(...): ...


# @router.post("/chat")
# async def chat(...): ...
