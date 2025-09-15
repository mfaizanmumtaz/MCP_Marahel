from fastapi import APIRouter, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import tempfile
import json
import logging
import os
import string
import random
import datetime
import asyncio
from ingestion_api.utils.pg_vector import pg_insertion, pg_deletion
from ingestion_api.db.postgres_connection import AsyncSession, get_db
import aiofiles
from sqlalchemy import select, update, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from ingestion_api.db.user_db import Collections_Dev, RawData
from ingestion_api.utils.ingestion_utils import IncomingFileProcessor
from ingestion_api.utils.uuid_validater import validate_uuid
from langchain_core.documents import Document
from ingestion_api.utils.count_tokens import count_tokens
from ingestion_api.utils.qdrant_class import QdrantInsertRetrievalAll
from ingestion_api.utils.csv_excel_uploader import CSVExcelHandler
from langchain_openai import OpenAIEmbeddings


from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

qdrant = QdrantInsertRetrievalAll()

embedder = OpenAIEmbeddings(model="text-embedding-3-small")
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


# FileHandler for cag.log
arabic_handler = logging.FileHandler(os.path.join(log_dir, "cag.log"))
arabic_handler.setFormatter(formatter)
logger.addHandler(arabic_handler)

cag_router = APIRouter()
ALLOWED_DOCS = {"docx", "doc", "pdf"}


@cag_router.post("/cag-ingestion")
async def cag_ingestion(
    files: List[UploadFile],
    chatbot_id: str = Form(...),
    llm: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # --- initial validation & setup (unchanged) ---
    if not files:
        raise HTTPException(400, "No files provided")
    if not validate_uuid(chatbot_id):
        raise HTTPException(422, "Invalid chatbot_id uuid format")
    if llm not in ["openai", "claude"]:
        raise HTTPException(422, "Invalid LLM; choose openai, claude.")

    logger.info(f"Starting CAG ingestion (chatbot: {chatbot_id}, llm: {llm})")

    try:
        processor = IncomingFileProcessor(
            chunk_size=int(os.getenv("chunk_size")),
            chunk_overlap=int(os.getenv("chunk_overlap")),
        )
    except Exception as e:
        logger.error(f"Chunk-size/env error: {e}")
        raise HTTPException(422, "please set chunk size and overlap in .env file")

    csv_excel_handler = CSVExcelHandler()

    # --- ensure Collections_Dev row exists ---
    col = (
        (
            await db.execute(
                select(Collections_Dev)
                .filter(Collections_Dev.chatbot_id == chatbot_id)
                .with_for_update()
            )
        )
        .scalars()
        .first()
    )

    if col and col.vectordb_name != "postgres":
        raise HTTPException(400, "chatbot_id already used for RAG chatbot")

    if not col:
        try:
            db.add(
                Collections_Dev(
                    llm=llm,
                    chatbot_id=chatbot_id,
                    vectordb_name="postgres",
                    embeddings_model=None,
                    collection_name=None,
                )
            )
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Integrity error: {e}")
            raise HTTPException(409, "Collection already exists")

    # --- process each file ---
    docs_all = []
    for upload in files:
        try:
            # Read into memory once
            content = await upload.read()
            if not content:
                raise HTTPException(422, f"File {upload.filename} is empty")

            # 1) Try CSV/Excel in-memory
            file_id = await csv_excel_handler.process_in_memory(
                chatbot_id, None, content, upload.filename
            )
            if file_id:
                logger.info(f"Stored sheet {upload.filename} as ID {file_id}")
                continue

            # 2) Fallback to doc/pdf splitting
            ext = upload.filename.lower().rsplit(".", 1)[-1]
            if ext not in ALLOWED_DOCS:
                raise HTTPException(
                    422,
                    f"Invalid file type: {ext}. Supported: PDF, DOCX, DOC, CSV, XLSX",
                )

            # write to temp
            fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(content)

            if ext == "docx":
                docs = await processor.get_docx_splits(
                    tmp_path, file_original_name=upload.filename
                )
            elif ext == "doc":
                docs = await processor.get_doc_splits(
                    tmp_path, file_original_name=upload.filename
                )
            else:
                docs = await processor.get_pdf_splits(
                    tmp_path, file_original_name=upload.filename
                )

            docs_all.extend(docs)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing {upload.filename}: {e}")
            raise HTTPException(422, f"Error processing {upload.filename}: {e}")
        finally:
            # cleanup temp if created
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                await aiofiles.os.remove(tmp_path)

    # --- if only CSV/Excel files were uploaded ---
    if not docs_all:
        return JSONResponse(
            {
                "message": "CSV/Excel files uploaded successfully",
                "chatbot_id": chatbot_id,
            },
            status_code=200,
        )

    # --- existing token-count & RawData logic for docs_all ---
    try:
        token_count = await count_tokens(docs_all, "cl100k_base", chatbot_id)
        if token_count > 200000:
            # await migrate_to_vectorstore(docs_all, chatbot_id, llm=llm, db=db)
            return JSONResponse(
                {
                    "message": "Data > 200k tokens. Cannot handle.",
                    "chatbot_id": chatbot_id,
                },
                status_code=400,
            )
    except Exception as e:
        logger.error(f"Token error: {e}")
        raise HTTPException(500, f"Error in token processing: {e}")

    try:
        serialized = [doc.__dict__ for doc in docs_all]

        # Separate PDF and non-PDF content
        pdf_content = []
        non_pdf_content = []

        for doc in serialized:
            if doc.get("metadata", {}).get("source", "").lower().endswith(".pdf"):
                pdf_content.append(doc)
            else:
                non_pdf_content.append(doc)

        # Store PDF content
        if pdf_content:
            db.add(RawData(chatbot_id=chatbot_id, data=json.dumps(pdf_content)))

        # Store non-PDF content normally
        if non_pdf_content:
            db.add(RawData(chatbot_id=chatbot_id, data=json.dumps(non_pdf_content)))

        await db.commit()

    except Exception as e:
        await db.rollback()
        logger.error(f"RawData DB error: {e}")
        raise HTTPException(500, "Error updating document data in database")

    return JSONResponse(
        {"message": "CAG Ingestion Successful!", "chatbot_id": chatbot_id},
        status_code=200,
    )


async def migrate_to_vectorstore(
    given_data, chatbot_id: str, llm: str, db: AsyncSession
):
    """
    Migrate given data to vector store with proper transaction handling,
    retries, and consistent session usage.
    """
    try:
        # Set timeouts (higher values for reliability)
        await db.execute(text("SET LOCAL statement_timeout = '30s'"))
        await db.execute(text("SET LOCAL lock_timeout = '30s'"))

        # Fetch raw data with locking
        result = await db.execute(
            select(RawData)
            .filter(RawData.chatbot_id == chatbot_id)
            .with_for_update(skip_locked=True)
        )
        raw_data_entry = result.scalars().first()

        # Merge documents
        docs = []
        if raw_data_entry and raw_data_entry.data:
            raw_whole_data = raw_data_entry.data
            existing_docs = [Document(**doc) for doc in json.loads(raw_whole_data)]
            docs = existing_docs + given_data
        else:
            docs = given_data

        # Create a unique collection name
        ts = datetime.datetime.now().strftime("%y%m%d_%H%M")
        rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        collection_name = f"collection_{ts}_{rand}_{chatbot_id}"

        # Insert into Qdrant

        await pg_insertion(docs, embedder, collection_name)

        # Retry loop for DB update in case of lock
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await db.execute(
                    update(Collections_Dev)
                    .where(Collections_Dev.chatbot_id == chatbot_id)
                    .values(
                        collection_name=collection_name,
                        vectordb_name="pgvector",
                        embeddings_model="openai",
                        llm=llm,
                    )
                )
                if raw_data_entry:
                    await db.delete(raw_data_entry)

                await db.commit()
                logger.info("Migration completed successfully")
                break  # Exit loop on success

            except SQLAlchemyError as db_error:
                await db.rollback()
                if (
                    "lock timeout" in str(db_error).lower()
                    and attempt < max_retries - 1
                ):
                    logger.warning(f"Lock timeout attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(2)
                else:
                    # Cleanup Qdrant collection if DB update fails
                    try:
                        await pg_deletion(collection_name)
                    except Exception as cleanup_error:
                        logger.error(f"Cleanup failed: {cleanup_error}")
                    logger.error(f"Database update failed: {db_error}")
                    raise

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        await db.rollback()
        raise
