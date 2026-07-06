"""
Sales Visual Backend — FastAPI Application Entry Point
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # ← ajoute ces deux lignes ici

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router, reports_router as admin_reports_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.documents import router as documents_router
from app.api.monday import router as monday_router
from app.api.reports import router as reports_router
from app.api.test_email import router as test_email_router
from app.api.visuals import router as visuals_router
from app.core.config import settings
from app.services.blob_service import ensure_container_exists

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="Sales Visual API",
    description="Backend service for Sales Visual — a sales analytics & visualization platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.BACKEND_CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(monday_router)
app.include_router(visuals_router)
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(documents_router)
app.include_router(reports_router)
app.include_router(test_email_router)
app.include_router(admin_router)
app.include_router(admin_reports_router)

Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.on_event("startup")
def startup() -> None:
    ensure_container_exists()


@app.get("/health")
async def health_check():
    return {"status": "ok"}
