from fastapi import APIRouter
from ingestion_api.api.endpoints.rag import rag_ingestion
from ingestion_api.api.endpoints.cag import cag_router

ingestion_api = APIRouter()

# Arabic Bot endpoints
ingestion_api.include_router(cag_router, tags=["Ingestion API"])
ingestion_api.include_router(rag_ingestion, tags=["Ingestion API"])
