from fastapi import APIRouter
from ingestion_api.api.endpoints.rag import rag_ingestion
from ingestion_api.api.endpoints.cag import cag_router
from ingestion_api.api.endpoints.content_extractor_api import content_extractor

ingestion_api = APIRouter()

ingestion_api.include_router(content_extractor, tags=["content Extractor"])

# Arabic Bot endpoints
ingestion_api.include_router(cag_router, tags=["Ingestion API"])
ingestion_api.include_router(rag_ingestion, tags=["Ingestion API"])
