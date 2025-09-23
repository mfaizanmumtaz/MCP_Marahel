from fastapi import APIRouter
from ingestion_api.api.endpoints.content_extractor_api import content_extractor

ingestion_api = APIRouter()

ingestion_api.include_router(content_extractor, tags=["content Extractor"])