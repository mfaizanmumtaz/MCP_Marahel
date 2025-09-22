from langchain_core.documents import Document
import tiktoken
from sqlalchemy import select
import json
from ingestion_api.db.models import RawData
from ingestion_api.db.connection import async_session
import logging
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
import os

# Set up log directory
log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)


# FileHandler for arabic_bot_utils.log
arabic_handler = logging.FileHandler(os.path.join(log_dir, "count_tokens.log"))
arabic_handler.setFormatter(formatter)
logger.addHandler(arabic_handler)


async def get_data_from_db(chatbot_id: str) -> List[str]:
    """
    Fetches raw data from the database for a given chatbot_id.

    Args:
        chatbot_id (str): The ID of the chatbot to fetch data for

    Returns:
        List[str]: List of document contents

    Raises:
        SQLAlchemyError: If there's a database error
        json.JSONDecodeError: If the stored data is not valid JSON
    """
    try:
        async with async_session() as session:
            try:
                # Get all records for the chatbot_id
                result = await session.execute(
                    select(RawData).filter(RawData.chatbot_id == chatbot_id)
                )
                raw_data_entries = result.scalars().all()

                if not raw_data_entries:
                    logger.info(f"No data found for chatbot_id: {chatbot_id}")
                    return []

                docs = []
                for entry in raw_data_entries:
                    if entry.data:
                        try:
                            raw_data = entry.data
                            entry_docs = [
                                i.page_content
                                for i in [
                                    Document(**doc) for doc in json.loads(raw_data)
                                ]
                            ]
                            docs.extend(entry_docs)
                        except json.JSONDecodeError as json_err:
                            logger.error(
                                f"JSON parsing error for chatbot_id {chatbot_id} entry: {str(json_err)}"
                            )
                            continue
                        except Exception as e:
                            logger.error(
                                f"Error processing document data for chatbot_id {chatbot_id} entry: {str(e)}"
                            )
                            continue

                return docs

            except SQLAlchemyError as db_err:
                logger.error(
                    f"Database error while fetching data for chatbot_id {chatbot_id}: {str(db_err)}"
                )
                raise

    except Exception as e:
        logger.error(
            f"Unexpected error in get_data_from_db for chatbot_id {chatbot_id}: {str(e)}"
        )
        raise


async def count_tokens(
    documents: List[Document], model_name: str, chatbot_id: str
) -> Optional[int]:
    """
    Returns the number of tokens in a text string.

    Args:
        documents (List[Document]): List of documents to count tokens for
        model_name (str): Name of the model to use for token counting
        chatbot_id (str): The ID of the chatbot

    Returns:
        Optional[int]: Number of tokens, or None if an error occurs

    Raises:
        ValueError: If model_name is invalid
        Exception: For other unexpected errors
    """
    try:
        # Validate inputs
        if not isinstance(documents, list):
            raise ValueError("documents must be a list")
        if not model_name:
            raise ValueError("model_name cannot be empty")
        if not chatbot_id:
            raise ValueError("chatbot_id cannot be empty")

        # Get document contents
        doc_contents = [
            doc.page_content for doc in documents if hasattr(doc, "page_content")
        ]

        try:
            # Get data from database
            db_contents = await get_data_from_db(chatbot_id)
        except Exception as db_err:
            logger.error(f"Error fetching data from database: {str(db_err)}")
            db_contents = []

        # Combine all text
        text = " ".join(doc_contents + db_contents)

        try:
            # Get encoding for model
            encoding = tiktoken.get_encoding(model_name)
            num_tokens = len(encoding.encode(text))
            logger.info(
                f"Successfully counted {num_tokens} tokens for chatbot_id: {chatbot_id}"
            )
            return num_tokens
        except Exception as token_err:
            logger.error(
                f"Error encoding text with tiktoken for model {model_name}: {str(token_err)}"
            )
            raise

    except Exception as e:
        logger.error(f"Error in count_tokens: {str(e)}")
        raise
