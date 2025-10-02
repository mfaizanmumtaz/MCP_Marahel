from fastapi import APIRouter
from ingestion_api.api.endpoints.content_extractor_api import content_extractor
from ingestion_api.api.endpoints.content_extractor_api_v2 import content_extractor_v2
from ingestion_api.api.endpoints.model_preferences_api import model_preferences_router

ingestion_api = APIRouter()

# V2 API - Enhanced with MIME validation, image detection, OCR, thumbnails
ingestion_api.include_router(content_extractor_v2, prefix="/content-extractor-v2", tags=["Content Extractor V2"])

# V1 API - Legacy support
ingestion_api.include_router(content_extractor, tags=["Content Extractor V1 (Legacy)"])

ingestion_api.include_router(model_preferences_router, tags=["Model Preferences"])