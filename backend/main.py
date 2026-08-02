import asyncio
import logging
import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

import auth_routes
import autodiscover_routes
import messages_routes
import notes_routes
import profile_routes
from database import initialize_database
from guest_retention import ensure_guest_user, guest_retention_loop
from oauth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SESSION_SAME_SITE,
    session_cookie_secure,
    session_secret,
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    path="/",
    same_site=SESSION_SAME_SITE,
    https_only=session_cookie_secure(),
)

app.include_router(autodiscover_routes.router)
app.include_router(profile_routes.router)
app.include_router(auth_routes.router)
app.include_router(notes_routes.router)
app.include_router(messages_routes.router)


@app.on_event("startup")
async def startup():
    initialize_database()
    ensure_guest_user()
    app.state.guest_retention_task = asyncio.create_task(guest_retention_loop())


@app.on_event("shutdown")
async def shutdown():
    task = app.state.guest_retention_task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@app.get("/health")
def health():
    return {"status": "ok"}
