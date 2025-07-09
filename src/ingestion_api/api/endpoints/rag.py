from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import UploadFile, Form, status, Depends
from ingestion_api.utils.ingestion_utils import IncomingFileProcessor
import tempfile
import random
import datetime
from sqlalchemy import select
from ingestion_api.db.postgres_connection import AsyncSession, get_db
import string
import os
from ingestion_api.utils.qdrant_class import QdrantInsertRetrievalAll
from langchain_core.documents import Document
from typing import List
from langchain_openai import OpenAIEmbeddings
import logging
from ingestion_api.db.user_db import Collections_Dev
from ingestion_api.utils.pg_vector import pg_insertion
from ingestion_api.utils.uuid_validater import validate_uuid
from sqlalchemy.future import select
import aiofiles
import aiofiles.os
from fastapi import HTTPException
from ingestion_api.utils.csv_excel_uploader import CSVExcelHandler
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())

csv_excel_handler = CSVExcelHandler()


log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:  # Prevent duplicate handlers
    arabic_handler = logging.FileHandler(os.path.join(log_dir, "arabic_bot.log"))
    arabic_handler.setFormatter(formatter)
    logger.addHandler(arabic_handler)

# 2. Configure query_classifier logger (for arabic_bot_utils.log)
classifier_logger = logging.getLogger("arabic_bot")
classifier_logger.setLevel(logging.INFO)
classifier_logger.propagate = False  # Prevent logs from going to parent loggers

if not classifier_logger.handlers:  # Prevent duplicate handlers
    classifier_handler = logging.FileHandler(
        os.path.join(log_dir, "arabic_bot_utils.log")
    )
    classifier_handler.setFormatter(formatter)
    classifier_logger.addHandler(classifier_handler)


qdrant = QdrantInsertRetrievalAll()
rag_ingestion = APIRouter()


@rag_ingestion.post("/rag-ingestion")
async def ingestion_file(
    files: List[UploadFile],
    llm: str = Form(...),
    chatbot_id: str = Form(...),
    chunk_size: int = Form(...),
    chunk_overlap: int = Form(...),
    embeddings_model: str = Form(...),
    vectorstore_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Process and ingest uploaded files into a vector database.
    Preserves initial collection configuration if already exists.
    """
    # --- validation ---
    if llm not in ["openai", "claude"]:
        return JSONResponse(
            {"message": "Invalid LLM; use openai, claude."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if not validate_uuid(chatbot_id):
        return JSONResponse(
            {"message": "Invalid chatbot_id UUID."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if chunk_overlap > chunk_size:
        return JSONResponse(
            {"message": "chunk_overlap cannot exceed chunk_size."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if vectorstore_name not in ["qdrant", "pgvector"]:
        # only check once, but we'll override if collection exists
        return JSONResponse(
            {"message": "Invalid vectorstore; use qdrant or pgvector."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    allowed_emb = ["openai"]
    if embeddings_model not in allowed_emb:
        return JSONResponse(
            {"message": "Invalid embedding model; please pass openai."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    processor = IncomingFileProcessor(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    logger.info(
        f"Starting RAG ingestion for {chatbot_id} (requested store: {vectorstore_name})"
    )

    try:
        # --- collection lookup ---
        result = await db.execute(
            select(Collections_Dev)
            .where(Collections_Dev.chatbot_id == chatbot_id)
            .with_for_update()
        )
        coll = result.scalars().first()
        if coll and coll.vectordb_name == "postgres":
            raise HTTPException(
                status_code=400, detail="chatbot_id already used for CAG chatbot"
            )

        if coll:
            # preserve original DB and embedding config
            used_store = coll.vectordb_name
            used_emb = coll.embeddings_model
            collection_name = coll.collection_name
            if used_emb:
                if used_emb == "openai":
                    embedder = OpenAIEmbeddings(
                        model="text-embedding-3-small",
                        api_key=os.getenv("OPENAI_API_KEY"),
                    )

        else:
            # new collection: use provided config and record it
            used_store = vectorstore_name
            ts = datetime.datetime.now().strftime("%y%m%d_%H%M")
            rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
            collection_name = f"collection_{ts}_{rand}_{chatbot_id}"
            if embeddings_model == "openai":
                embedder = OpenAIEmbeddings(
                    model="text-embedding-3-small", api_key=os.getenv("OPENAI_API_KEY")
                )
                used_emb = "openai"

            # commit new collection
            db.add(
                Collections_Dev(
                    llm=llm,
                    chatbot_id=chatbot_id,
                    vectordb_name=used_store,
                    embeddings_model=used_emb,
                    collection_name=collection_name,
                )
            )
            await db.commit()

        # --- file reading & splitting ---
        contents, exts = [], []
        for f in files:
            b = await f.read()
            ext = f.filename.lower().rsplit(".", 1)[-1]
            if not b:
                return JSONResponse(
                    {"message": "Empty file found."},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if ext not in ["docx", "doc", "pdf", "txt"]:
                return JSONResponse(
                    {"message": "Allowed: PDF, DOCX, DOC, TXT."},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            contents.append(b)
            exts.append(ext)

        docs: List[Document] = []
        for i, f in enumerate(files):
            fd, tmp = tempfile.mkstemp(suffix=f".{exts[i]}")
            try:
                with os.fdopen(fd, "wb") as tf:
                    tf.write(contents[i])
                if exts[i] == "docx":
                    split = await processor.get_docx_splits(
                        tmp, file_original_name=f.filename
                    )
                elif exts[i] == "doc":
                    split = await processor.get_doc_splits(
                        tmp, file_original_name=f.filename
                    )
                elif exts[i] == "pdf":
                    split = await processor.get_pdf_splits(
                        tmp, file_original_name=f.filename
                    )
                else:
                    async with aiofiles.open(tmp, "r", encoding="utf-8") as tf:
                        txt = await tf.read()
                        split = [
                            Document(page_content=txt, metadata={"source": f.filename})
                        ]
                docs.extend(split)
            except Exception as e:
                logger.error(f"Error processing {f.filename}: {e}")
                return JSONResponse(
                    {"message": f"Error processing {exts[i]}: {e}"},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            finally:
                await aiofiles.os.remove(tmp)

        # --- insert into vector store ---
        if used_store == "pgvector":
            try:
                await pg_insertion(docs, embedder, collection_name)
            except Exception as e:
                logger.error(f"Error during pgvector insertion: {e}")
                return JSONResponse(
                    {"message": f"Error during pgvector insertion: {e}"},
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            try:
                await qdrant.insertion(docs, embedder, collection_name)
            except Exception as e:
                logger.error(f"Error during Qdrant insertion: {e}")
                return JSONResponse(
                    {"message": f"Error during Qdrant insertion: {e}"},
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.info(f"Data inserted → {used_store}:{collection_name}")

        return JSONResponse(
            {"message": "RAG Ingestion Successful!", "chatbot_id": chatbot_id},
            status_code=status.HTTP_200_OK,
        )

    except Exception as ex:
        await db.rollback()
        logger.error(f"RAG ingestion error: {ex}")
        return JSONResponse(
            {"message": f"An error occurred: {ex}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
