from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    chatbot_id: str
    user_id: str


class MessageResponse(BaseModel):
    role: str
    content: str
    type: str


class QueryResponse(BaseModel):
    response_text: str
