"""
Model Preferences API

Simple API for admins to set/update model provider preferences for tenants.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from ingestion_api.db.connection import get_db
from ingestion_api.db.models import ModelPreference, Tenant
import datetime

logger = logging.getLogger(__name__)

# Create APIRouter instance
model_preferences_router = APIRouter()


class ModelPreferenceRequest(BaseModel):
    """Request model for setting/updating model preferences"""
    tenant_id: str = Field(..., description="Tenant identifier")
    model_provider: str = Field(..., description="Model provider: 'openai' or 'gemini'")


def validate_model_provider(model_provider: str) -> bool:
    """Validate if model provider is supported"""
    valid_providers = {"openai", "gemini"}
    return model_provider.lower() in valid_providers


@model_preferences_router.post("/model-preference")
async def set_or_update_model_preference(
    request: ModelPreferenceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Set or update model provider preference for a tenant.

    - If tenant doesn't exist: Returns 404 error
    - If tenant exists and preference exists: Updates it
    - If tenant exists and preference doesn't exist: Creates it
    - Default provider is 'openai' if not set

    Args:
        tenant_id: Tenant identifier (must exist in tenants table)
        model_provider: 'openai' or 'gemini'

    Returns:
        Success message with preference details

    Raises:
        HTTPException 400: Invalid model_provider
        HTTPException 404: Tenant does not exist
        HTTPException 500: Database error
    """
    try:
        tenant_id = request.tenant_id
        model_provider = request.model_provider

        # Validate model provider
        if not validate_model_provider(model_provider):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_provider '{model_provider}'. Must be 'openai' or 'gemini'"
            )

        # Check if tenant exists
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.tenant_id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant '{tenant_id}' does not exist. Please create the tenant first."
            )

        # Check if preference exists
        model_pref_result = await db.execute(
            select(ModelPreference).where(ModelPreference.tenant_id == tenant_id)
        )
        model_pref = model_pref_result.scalar_one_or_none()

        if model_pref:
            # Update existing preference
            old_provider = model_pref.model_provider
            model_pref.model_provider = model_provider.lower()
            model_pref.updated_at = datetime.datetime.utcnow()
            action = "updated"

            logger.info(f"Updated model preference for tenant {tenant_id}: {old_provider} -> {model_provider}")
        else:
            # Create new preference (only if tenant exists)
            model_pref = ModelPreference(
                tenant_id=tenant_id,
                model_provider=model_provider.lower()
            )
            db.add(model_pref)
            action = "created"

            logger.info(f"Created model preference for tenant {tenant_id}: {model_provider}")

        await db.commit()
        await db.refresh(model_pref)

        return JSONResponse(
            content={
                "message": f"Model preference {action} successfully",
                "tenant_id": tenant_id,
                "model_provider": model_pref.model_provider,
                "updated_at": model_pref.updated_at.isoformat()
            },
            status_code=200
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error setting model preference: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set model preference: {str(e)}"
        )