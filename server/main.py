"""ASGI entrypoint."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.routes import router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Document Parser", version="0.2.0")

_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
# Browsers reject "*" + credentials=True; force credentials off in that case.
if _origins == ["*"]:
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
