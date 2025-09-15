from pydantic import BaseModel
from typing import Optional


class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    user_id: Optional[str] = None


class MessageResponse(BaseModel):
    role: str
    content: str
    type: str


class QueryResponse(BaseModel):
    response_text: str
