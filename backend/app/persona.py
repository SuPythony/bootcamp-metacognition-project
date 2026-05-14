"""POST /persona/create and POST /persona/reset.

/persona/create returns { status: "exists" | "pending", session_id?, persona? }.
On "pending" the frontend continues the interview through standard /chat against
the returned session_id, using the reserved domain "persona".
"""

from fastapi import APIRouter

router = APIRouter()


# @router.post("/persona/create")
# async def persona_create(...): ...


# @router.post("/persona/reset")
# async def persona_reset(...): ...
