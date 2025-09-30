from fastapi import APIRouter
from ingestion_api.api.endpoints.content_extractor_api import content_extractor
from ingestion_api.api.endpoints.model_preferences_api import model_preferences_router

ingestion_api = APIRouter()

ingestion_api.include_router(content_extractor, tags=["Content Extractor"])
ingestion_api.include_router(model_preferences_router, tags=["Model Preferences"])