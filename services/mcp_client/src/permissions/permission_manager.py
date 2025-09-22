from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ingestion_api.db.connection import async_session
from ingestion_api.db.models import Tenant
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class PermissionManager:
    """
    Manages tool permissions for tenants based on admin settings.
    Filters available tools based on tenant access permissions.
    """

    def __init__(self):
        self.tool_mapping = {
            "summary_access": ["get_summarization"],
            "translation_access": ["get_translation"],
            "rag_access": ["rag_knowledge_base"],
            "cag_access": ["get_knowledge_base"]
        }

    async def get_tenant_permissions(self, tenant_id: str) -> Dict[str, bool]:
        """
        Retrieve tenant permissions from database.

        Args:
            tenant_id: The tenant identifier

        Returns:
            Dictionary containing permission flags for each tool category
        """
        try:
            async with async_session() as session:
                # Find tenant by tenant_id
                result = await session.execute(
                    select(Tenant).where(Tenant.tenant_id == tenant_id)
                )
                tenant = result.scalar_one_or_none()

                if not tenant:
                    logger.warning(f"Tenant '{tenant_id}' not found")
                    return {
                        "summary_access": False,
                        "translation_access": False,
                        "rag_access": False,
                        "cag_access": False
                    }

                return {
                    "summary_access": tenant.summary_access,
                    "translation_access": tenant.translation_access,
                    "rag_access": tenant.rag_access,
                    "cag_access": tenant.cag_access
                }

        except Exception as e:
            logger.error(f"Error retrieving tenant permissions: {str(e)}")
            # Return all False on error for security
            return {
                "summary_access": False,
                "translation_access": False,
                "rag_access": False,
                "cag_access": False
            }

    async def filter_tools_by_permissions(self, tools: List[Any], tenant_id: str) -> List[Any]:
        """
        Filter tools based on tenant permissions.

        Args:
            tools: List of available tools from MCP client
            tenant_id: The tenant identifier

        Returns:
            Filtered list of tools based on permissions.
            Returns empty list if all permissions are False.
        """
        try:
            # Get tenant permissions
            permissions = await self.get_tenant_permissions(tenant_id)

            # Check if all permissions are False
            if not any(permissions.values()):
                logger.info(f"All tools disabled for tenant '{tenant_id}'. Returning empty tool list.")
                return []

            # Check if all permissions are True
            if all(permissions.values()):
                logger.info(f"All tools enabled for tenant '{tenant_id}'. Returning all tools.")
                return tools

            # Filter tools based on permissions
            allowed_tool_names = set()
            for permission_key, has_access in permissions.items():
                if has_access and permission_key in self.tool_mapping:
                    allowed_tool_names.update(self.tool_mapping[permission_key])

            # Filter the actual tools
            filtered_tools = []
            for tool in tools:
                # Check if tool name matches any allowed tool
                tool_name = getattr(tool, 'name', str(tool))
                if tool_name in allowed_tool_names:
                    filtered_tools.append(tool)

            logger.info(f"Filtered tools for tenant '{tenant_id}': {[getattr(t, 'name', str(t)) for t in filtered_tools]}")
            return filtered_tools

        except Exception as e:
            logger.error(f"Error filtering tools for tenant '{tenant_id}': {str(e)}")
            # Return empty list on error for security
            return []

    async def check_tool_permission(self, tool_name: str, tenant_id: str) -> bool:
        """
        Check if a specific tool is allowed for a tenant.

        Args:
            tool_name: Name of the tool to check
            tenant_id: The tenant identifier

        Returns:
            True if tool is allowed, False otherwise
        """
        try:
            permissions = await self.get_tenant_permissions(tenant_id)

            # Find which permission category this tool belongs to
            for permission_key, tool_names in self.tool_mapping.items():
                if tool_name in tool_names:
                    return permissions.get(permission_key, False)

            # Tool not found in mapping, deny access
            logger.warning(f"Tool '{tool_name}' not found in permission mapping")
            return False

        except Exception as e:
            logger.error(f"Error checking tool permission for '{tool_name}', tenant '{tenant_id}': {str(e)}")
            return False


# Global permission manager instance
permission_manager = PermissionManager()