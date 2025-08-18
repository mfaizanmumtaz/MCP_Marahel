from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Union


class QueryInput(BaseModel):
    query: str
    chatbot_id: str
    user_id: str
    session_id: Optional[str] = None
    guidelines: Optional[str] = None
    user_input: Optional[str] = None
    user_output: Optional[str] = None


class DeleteCollectionInput(BaseModel):
    chatbot_id: str
    session_id: Optional[str] = None


class CollectionInput(BaseModel):
    chatbot_id: str


class CustomInstructionInput(BaseModel):
    chatbot_id: str
    guidelines: str
    user_input: str
    user_output: str


class ResponseRegeneration(BaseModel):
    query: str
    instructions: str
    response: str
    chatbot_id: str
    user_id: str


class GreetingResponse(BaseModel):
    """You classify user queries as "yes" if they are solely or primarily greetings and as "no" if they include additional context. For "yes," generate a greeting response; for "no," return statusCode:404 as the response."""

    is_greeting: Literal["yes", "no"] = Field(
        ...,
        description="Classify if input is purely a greeting ('yes') or contains additional context ('no')",
    )
    response: str = Field(
        ...,
        description="If is_greeting='yes', provide a friendly greeting response. If is_greeting='no', return 'statusCode:404'",
    )


class TextToSpeechRequest(BaseModel):
    text: str
    voice_type: str


class PlayHTTextToSpeechRequest(BaseModel):
    text: str


# class PagesWithFilename(BaseModel):
#     filename: str = Field(description="Filename from which the response was generated.")
#     pages: list[int] = Field(description="Pages from which the response was generated.")


# class ResponseFormatterForCag(BaseModel):
#     answer: Optional[str,"statuscode404"] = Field(description="The answer to the user question.")
#     sources: list[PagesWithFilename] = Field(
#         description="Sources from which the response was generated."
#     )


class PagesWithFilename(BaseModel):
    filename: str = Field(
        ..., description="Filename from which the response was generated."
    )
    pages: List[int] = Field(
        ..., description="Pages from which the response was generated."
    )


class ResponseFormatterForCag(BaseModel):
    answer: Union[str, Literal["statuscode404"]] = Field(
        ...,
        description="The answer to the user question, or the literal 'statuscode404' if no information is available.",
    )
    sources: List[PagesWithFilename] = Field(
        ..., description="Sources from which the response was generated."
    )
