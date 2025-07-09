import os

# Add the project root to Python path
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
# if project_root not in sys.path:
#     sys.path.insert(0, project_root)

import asyncio
import logging
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag_cag_agent.utils.document_relevance_checker import filter_relevant_documents
from rag_cag_agent.prompts.prompts_for_rag import (
    system_prompt_for_rag_based_generation as system_prompt_for_rag,
    system_prompt_for_rag_based_generation_with_custom_instructions as system_prompt_for_rag_history,
)
from rag_cag_agent.prompts.prompts_for_cag import (
    system_prompt_for_cag_based_generation as system_prompt_for_cag,
    system_prompt_for_cag_based_generation_with_custom_instructions as system_prompt_for_cag_history,
)
from rag_cag_agent.prompts.generals_prompts import query_standalone_prompt
from langchain_postgres.vectorstores import PGVector
from rag_cag_agent.schemas.arbic_bot_schema import ResponseFormatterForCag
from rag_cag_agent.utils.history_formatter import HistoryFormatter
from rag_cag_agent.utils.translation_utils import translate_text
from langdetect import detect, DetectorFactory

# Optional import for Qdrant - fallback if not available
try:
    from langchain_qdrant.qdrant import QdrantVectorStore
except ImportError:
    QdrantVectorStore = None

from openai import OpenAI
import aiofiles
import aiohttp

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture detailed logs
formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)
log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(os.path.join(log_dir, "arabic_bot_utils.log"))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Ensure consistent results by setting a seed
DetectorFactory.seed = 0
logger.info("DetectorFactory seed set to 0.")


def detect_language(text: str) -> str:
    """Detect if text is primarily Arabic or English using langdetect."""
    if not text.strip():
        logger.debug(
            "Empty text received for language detection; defaulting to English."
        )
        return "english"  # Default to English for empty text

    try:
        lang = detect(text)
        logger.debug(f"Detected language '{lang}' for text: {text[:30]}...")
        if lang == "ar":
            return "arabic"
        elif lang == "en":
            return "english"
        else:
            logger.debug(
                "Language detected is neither 'ar' nor 'en'; defaulting to Arabic."
            )
            return "arabic"  # Default to Arabic for any other language
    except Exception as ex:
        logger.error(
            f"Language detection error for text: {text[:30]}... Error: {str(ex)}"
        )
        return "arabic"  # Default to Arabic in case of errors


def _combine_documents3(docs, document_separator="\n\n"):
    try:
        logger.info(f"Combining {len(docs) if docs else 0} documents")
        if docs:
            combined_documents = document_separator.join(
                [doc.page_content for doc in docs]
            )
            return combined_documents
    except Exception as ex:
        logger.error(f"Error combining documents: {str(ex)}")
        raise


history_formatter = HistoryFormatter()


def ExtractRelevantMetadata(docs):
    source_map = {}
    for doc in docs:
        filename = doc.metadata.get("source", "")
        page = doc.metadata.get("page", 1)
        source_map.setdefault(filename, set()).add(page)

    # sources = [
    #     {"documents": {"filename": filename, "pages": sorted(list(pages))}}
    #     for filename, pages in source_map.items()
    # ]

    sources = [
        {"filename": filename, "pages": sorted(pages)}
        for filename, pages in source_map.items()
    ]

    logger.info(
        f"Extracted metadata from {len(docs)} documents into {len(sources)} source entries"
    )
    return sources


def edge_case_handler(language):
    if language == "english":
        sources = [
            {
                "filename": "No information is Available",
                "pages": [],
            }
        ]
        return (
            "I don't have enough information to answer that question accurately.",
            sources,
        )
    else:
        sources = [
            {
                "filename": "لا توجد معلومات متاحة",
                "pages": [],
            }
        ]
        return (
            "لا أملك معلومات كافية للإجابة على هذا السؤال بدقة.",
            sources,
        )


# Rag Function
async def get_response(
    original_query,
    database,
    chat_history,
    prompt,
    llm_model,
    instructions=None,
    previous_response=None,
):
    language = detect_language(original_query)
    loop = asyncio.get_event_loop()

    try:
        formatted_chat_history_for_response = (
            history_formatter.general_history_formatter(chat_history)
        )

        # Check if database is a vector store (handle case where QdrantVectorStore is None)
        vector_store_types = (PGVector,)
        if QdrantVectorStore is not None:
            vector_store_types = (QdrantVectorStore, PGVector)

        if isinstance(database, vector_store_types):
            logger.info(f"Processing query: {original_query[:10]}...")

            template = ChatPromptTemplate.from_template(query_standalone_prompt)
            chain = template | llm_model | StrOutputParser()

            if chat_history:
                logger.debug("Chat history is present; generating standalone query.")
                compromized_query = await chain.ainvoke(
                    {
                        "question": original_query,
                        "chat_history": history_formatter.format_history_for_standalone_query(
                            chat_history
                        ),
                    }
                )
            else:
                compromized_query = original_query

            retrieved_documents = await database.asimilarity_search(
                query=compromized_query, k=5
            )

            docs = await loop.run_in_executor(
                None,
                lambda: filter_relevant_documents(
                    original_query, retrieved_documents, llm_model
                ),
            )

            if not docs:
                logger.warning("No relevant context found for query")
                return edge_case_handler(language=language)

        else:
            docs = database

        # Check if database is a vector store (handle case where QdrantVectorStore is None)
        vector_store_types = (PGVector,)
        if QdrantVectorStore is not None:
            vector_store_types = (QdrantVectorStore, PGVector)

        if isinstance(database, vector_store_types):
            # For Rag Response
            sources = ExtractRelevantMetadata(docs)
            combined_context = _combine_documents3(docs)

            if instructions is None:
                if prompt is None:
                    policy_prompt = ChatPromptTemplate(
                        [
                            ("system", system_prompt_for_rag),
                            *formatted_chat_history_for_response,
                            ("user", "<query> {original_query} </query>"),
                        ]
                    )
                    chain = policy_prompt | llm_model
                    chain_params = {
                        "original_query": original_query,
                        "context": combined_context,
                        "language": language,
                    }
                else:
                    policy_prompt = ChatPromptTemplate(
                        [
                            (
                                "system",
                                system_prompt_for_rag_history,
                            ),
                            *formatted_chat_history_for_response,
                            ("user", "<query> {original_query} </query>"),
                        ]
                    )

                    chain = policy_prompt | llm_model
                    chain_params = {
                        "original_query": original_query,
                        "context": combined_context,
                        "language": language,
                        "custom_instructions": prompt,
                    }

                logger.info("Invoking LLM chain with prepared parameters.")
                response_obj = await chain.ainvoke(chain_params)
                response = response_obj.content
                logger.info("Successfully generated response with source information")

                return response, sources

            else:
                policy_prompt = ChatPromptTemplate(
                    [
                        ("system", "system_prompt_for_response_regeneration"),
                        *formatted_chat_history_for_response,
                        ("user", "<query> {original_query} </query>"),
                    ]
                )
                chain = policy_prompt | llm_model
                chain_params = {
                    "original_query": original_query,
                    "context": combined_context,
                    "custom_instructions": instructions,
                    "previous_response": previous_response,
                }
                logger.info("Invoking improvement LLM chain.")
                response_obj = await chain.ainvoke(chain_params)
                response = response_obj.content
                logger.info("Successfully improved the response.")
                return response, sources

        else:
            # For Cag Response

            if instructions is None:
                if prompt is None:
                    policy_prompt = ChatPromptTemplate(
                        [
                            ("system", system_prompt_for_cag),
                            *formatted_chat_history_for_response,
                            (
                                "user",
                                """<query> {original_query} </query> \n# Dataset

<dataset>
{context}
</dataset>

# Few-Shot Example For language Handling
<user> كيف حالك؟ </user>
<ai> Arabic reply </ai>

<user> How are you? </user>
<ai> English reply </ai>

<user>Hi, كيف الحال؟</user>
<ai> Arabic reply </ai>

<user> If the query is irrelevant, meaning there is no data in the context to answer the user question. Query could be in the any language.</user>
<ai> statuscode404 </ai>

- If the query is irrelevant, meaning there is no data in the context to answer the user question, return just "statuscode404" with no extra text.""",
                            ),
                        ]
                    )
                    chain = policy_prompt | llm_model.with_structured_output(
                        ResponseFormatterForCag
                    )
                    chain_params = {
                        "original_query": original_query,
                        "context": docs,
                        "language": language,
                    }
                else:
                    policy_prompt = ChatPromptTemplate(
                        [
                            (
                                "system",
                                system_prompt_for_cag_history,
                            ),
                            *formatted_chat_history_for_response,
                            ("user", "<query> {original_query} </query>"),
                        ]
                    )

                    chain = policy_prompt | llm_model.with_structured_output(
                        ResponseFormatterForCag
                    )
                    chain_params = {
                        "original_query": original_query,
                        "context": docs,
                        "language": language,
                        "custom_instructions": prompt,
                    }

                response_obj = await chain.ainvoke(chain_params)
                answer = response_obj.answer
                if answer == "statuscode404":
                    return edge_case_handler(language=language)
                else:
                    # Check if the response language matches the query language
                    response_language = detect_language(answer)
                    if response_language != language:
                        # Translate the response to match the query language
                        answer = await translate_text(answer, language)
                        logger.info(
                            f"Translated response from {response_language} to {language}"
                        )

                    formatted_response = {
                        "response": answer,
                        "sources": [
                            {"filename": source.filename, "pages": source.pages}
                            for source in response_obj.sources
                        ],
                    }
                    logger.info(
                        "Successfully generated response with source information"
                    )

                    return formatted_response.get("response"), formatted_response.get(
                        "sources"
                    )

            else:
                policy_prompt = ChatPromptTemplate(
                    [
                        ("system", "system_prompt_for_response_regeneration_for_cag"),
                        *formatted_chat_history_for_response,
                        ("user", "<query> {original_query} </query>"),
                    ]
                )
                chain = policy_prompt | llm_model.with_structured_output(
                    ResponseFormatterForCag
                )
                chain_params = {
                    "original_query": original_query,
                    "context": docs,
                    "custom_instructions": instructions,
                    "previous_response": previous_response,
                }
                response_obj = await chain.ainvoke(chain_params)
                answer = response_obj.answer
                if answer == "statuscode404":
                    return edge_case_handler(language=language)
                else:
                    # Check if the response language matches the query language
                    response_language = detect_language(answer)
                    if response_language != language:
                        # Translate the response to match the query language
                        answer = await translate_text(answer, language)
                        logger.info(
                            f"Translated response from {response_language} to {language}"
                        )

                    formatted_response = {
                        "response": answer,
                        "sources": [
                            {"filename": source.filename, "pages": source.pages}
                            for source in response_obj.sources
                        ],
                    }
                    logger.info(
                        "Successfully generated response with source information"
                    )

                    return formatted_response.get("response"), formatted_response.get(
                        "sources"
                    )

    except Exception as ex:
        logger.error(f"Error generating response: {str(ex)}")
        return f"An error occurred while processing your request: {str(ex)}", [
            {"filename": "Error processing request", "pages": []}
        ]


# Speech to text API
client = OpenAI()


async def speech_to_text_api(file_path):
    """
    Convert speech audio file to text using OpenAI's Whisper model.

    Args:
        file_path: Path to the audio file

    Returns:
        str: Transcribed text
    """
    loop = asyncio.get_event_loop()
    try:
        async with aiofiles.open(file_path, "rb") as audio_file:
            audio_content = await audio_file.read()
        transcription = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-1", file=("audio.wav", audio_content, "audio/wav")
            ),
        )
        logger.info(f"Successfully transcribed audio from {file_path}")
        return transcription.text
    except Exception as e:
        logger.error(f"Error in speech-to-text conversion for {file_path}: {str(e)}")
        raise


async def text_to_speech_api(text, output_path, voice_type):
    """
    Convert text to speech using OpenAI's TTS API.

    Args:
        text: Text to convert to speech
        output_path: Path to save the output audio file
        voice_type: Voice type to use for TTS

    Returns:
        bool: True if successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.audio.speech.create(
                model="tts-1-hd", voice=voice_type, input=text
            ),
        )
        audio_data = await loop.run_in_executor(None, response.read)
        async with aiofiles.open(output_path, "wb") as file:
            await file.write(audio_data)
        logger.info(f"Successfully converted text to speech at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error in text-to-speech conversion: {str(e)}")
        return False


async def playht_text_to_speech_api(text, output_path, voice_type):
    """
    Convert text to speech using the PlayHT API.

    Args:
        text: Text to convert to speech
        output_path: Path to save the output audio file
        voice_type: Voice type to use ('male' or 'female')

    Returns:
        bool: True if successful, False otherwise
    """
    voices = {
        "male": "s3://voice-cloning-zero-shot/d82d246c-148b-457f-9668-37b789520891/adolfosaad/manifest.json",
        "female": "s3://voice-cloning-zero-shot/a59cb96d-bba8-4e24-81f2-e60b888a0275/charlottenarrativesaad/manifest.json",
    }.get(voice_type)

    language = detect_language(text)

    try:
        url = "https://api.play.ht/api/v2/tts/stream"
        payload = {
            "text": text,
            "voice": voices,
            "output_format": "mp3",
            "quality": "high",
            "language": language,
            "voice_engine": "PlayDialog",
        }

        headers = {
            "accept": "audio/mpeg",
            "content-type": "application/json",
            "AUTHORIZATION": os.getenv("PLAYHT_API_KEY"),
            "X-USER-ID": os.getenv("PLAYHT_USER_ID"),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    async with aiofiles.open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                await f.write(chunk)
                    logger.info(
                        f"Successfully converted text to speech with PlayHT at {output_path}"
                    )
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"PlayHT API error: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Error in PlayHT text-to-speech conversion: {str(e)}")
        return False
