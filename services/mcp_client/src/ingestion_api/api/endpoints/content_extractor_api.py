import os
import tempfile
import asyncio
import json
from typing import List, Optional
from pathlib import Path
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

# Import your UniversalFileLoader class
from services.data_extraction_to_text import UniversalFileLoader

# Import database dependencies
from ingestion_api.db.connection import get_db
from ingestion_api.db.models import KnowledgeBase, Tenant
from sqlalchemy import select

# RAG vector store imports
from ingestion_api.utils.pg_vector import pg_insertion
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import random
from langchain_text_splitters import CharacterTextSplitter

import string
import datetime

from config.settings import settings

logger = logging.getLogger(__name__)

# Create APIRouter instance
content_extractor = APIRouter()

# Initialize RAG components
embedder = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL)

# Global loader instance (will be initialized in main.py)
loader: Optional[UniversalFileLoader] = None


async def get_loader() -> UniversalFileLoader:
    """Dependency to get the loader instance"""
    global loader
    if loader is None:
        # Initialize loader if not already done
        loader = UniversalFileLoader(openai_api_key=settings.OPENAI_API_KEY, openrouter_api_key=settings.OPENROUTER_API_KEY)
        logger.info("Loader initialized in dependency")
    return loader



async def save_upload_file(upload_file: UploadFile, destination_path: str) -> str:
    """Save uploaded file to temporary location"""
    try:
        with open(destination_path, "wb") as buffer:
            content = await upload_file.read()
            buffer.write(content)
        return destination_path
    except Exception as e:
        logger.error(f"Error saving file {upload_file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


def validate_file_extension(filename: str) -> bool:
    """Validate if file extension is supported"""
    supported_extensions = {
        ".pdf",
        ".pptx",
        ".docx",
        ".doc",
        ".mp3",
        ".wav",
        ".xlsx",
        ".xls",
        ".csv",
    }
    file_extension = Path(filename).suffix.lower()
    return file_extension in supported_extensions


def validate_file_size(file: UploadFile) -> tuple[bool, str]:
    """
    Validate file size based on file type
    PDF, DOC, DOCX, PPTX files will be compressed if > 10MB
    Excel and CSV have strict 50MB limits
    Audio files have 200MB limit with WAV compression available

    Args:
        file: UploadFile object

    Returns:
        tuple: (is_valid, error_message)
    """
    if not file.size:
        return True, ""

    file_extension = Path(file.filename).suffix.lower()
    file_size_mb = file.size / (1024 * 1024)  # Convert bytes to MB

    # Define size limits in MB
    compressible_document_limit = 200  # PDF, DOC, DOCX, PPTX files (will be compressed)
    excel_csv_limit = 50  # Excel, CSV files (strict limit, no compression)
    audio_size_limit = 200  # WAV, MP3 files

    # Compressible document files (PDF, DOC, DOCX, PPTX) - allow up to 200MB, will compress automatically
    compressible_extensions = {".pdf", ".doc", ".docx", ".pptx"}
    # Excel and CSV files (strict 50MB limit, no compression)
    excel_csv_extensions = {".xlsx", ".xls", ".csv"}
    # Audio files (200MB limit, WAV can be compressed)
    audio_extensions = {".mp3", ".wav"}

    if file_extension in compressible_extensions:
        if file_size_mb > compressible_document_limit:
            return (
                False,
                f"File '{file.filename}' size ({file_size_mb:.1f}MB) exceeds the maximum allowed size of {compressible_document_limit}MB for {file_extension.upper()} files.",
            )
    elif file_extension in excel_csv_extensions:
        if file_size_mb > excel_csv_limit:
            return (
                False,
                f"File '{file.filename}' size ({file_size_mb:.1f}MB) exceeds the maximum allowed size of {excel_csv_limit}MB for Excel/CSV files.",
            )
    elif file_extension in audio_extensions:
        if file_size_mb > audio_size_limit:
            return (
                False,
                f"File '{file.filename}' size ({file_size_mb:.1f}MB) exceeds the maximum allowed size of {audio_size_limit}MB for audio files.",
            )

    return True, ""


@content_extractor.post("/extract-files")
async def extract_multiple_files(
    files: List[UploadFile] = File(...),
    tenant_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    summary_access: bool = Form(...),
    translation_access: bool = Form(...),
    rag_access: bool = Form(...),
    cag_access: bool = Form(...),
    file_loader: UniversalFileLoader = Depends(get_loader),
    db: AsyncSession = Depends(get_db),
):
    if not user_id:
        user_id = None

    """
    Extract text from multiple uploaded files and save to knowledge_base table

    Args:
        request: FastAPI request object (used to extract files from form data)
        tenant_id: Tenant identifier (will be created if doesn't exist)
        user_id: Optional user identifier (if None, content is shared across all users in tenant)
        summary_access: Enable summary access (required)
        translation_access: Enable translation access (required)
        rag_access: Enable RAG access (required)
        cag_access: Enable CAG access (required)
        file_loader: UniversalFileLoader dependency
        db: Database session

    Returns:
        JSON response with success status and number of files processed

    Note:
        Files are required. At least one file must be uploaded.
        Files are extracted from form data and validated automatically.
    """
    if len(files) > 10:  # Limit number of files for performance
        raise HTTPException(
            status_code=400, detail="Maximum 10 files allowed per request"
        )

    # Find or create tenant using the new schema
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        # Create new tenant with provided tenant_id and optional user_id
        tenant = Tenant(
            tenant_id=tenant_id,  # Custom tenant identifier
            user_id=user_id,  # Optional user who created the tenant
            summary_access=summary_access,
            translation_access=translation_access,
            rag_access=rag_access,
            cag_access=cag_access,
        )
        db.add(tenant)
        await db.flush()  # Get the UUID without committing
        logger.info(f"Created new tenant: {tenant_id}")
    else:
        # Existing tenant - check if permissions need updating
        # Update permissions if they differ from current values
        tenant.summary_access = summary_access
        tenant.translation_access = translation_access
        tenant.rag_access = rag_access
        tenant.cag_access = cag_access

    # Use the actual UUID for foreign key
    final_tenant_id = str(tenant.id)

    # Always create pgvector collection name regardless of permissions
    pgvector_collection_name = None

    # Check if collection name already exists
    existing_entry = await db.execute(
        select(KnowledgeBase.pgvector_collection_name)
        .where(
            KnowledgeBase.tenant_id == final_tenant_id,
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.pgvector_collection_name.isnot(None),
        )
        .limit(1)
    )
    existing_collection = existing_entry.scalar_one_or_none()

    if existing_collection:
        # Reuse existing collection name
        pgvector_collection_name = existing_collection
    else:
        # No existing collection - create new one
        ts = datetime.datetime.now().strftime("%y%m%d_%H%M")
        rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        if user_id:
            pgvector_collection_name = (
                f"pg_collection_{ts}_{rand}_{tenant_id}_{user_id}"
            )
        else:
            pgvector_collection_name = f"pg_collection_{ts}_{rand}_{tenant_id}_shared"


    processed_files = []
    temp_file_paths = []
    total_saved = 0

    try:
        # Validate all files first (extension and size)
        for file in files:
            if not validate_file_extension(file.filename):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{file.filename}'. Supported formats: {', '.join(['.pdf', '.pptx', '.docx', '.doc', '.mp3', '.wav', '.xlsx', '.xls', '.csv'])}",
                )

            # Validate file size
            is_valid_size, size_error = validate_file_size(file)
            if not is_valid_size:
                raise HTTPException(status_code=400, detail=size_error)

        # Save all files to temporary locations
        file_tasks = []
        for file in files:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(file.filename).suffix
            ) as temp_file:
                temp_file_path = temp_file.name
                temp_file_paths.append((temp_file_path, file.filename))
                file_tasks.append(save_upload_file(file, temp_file_path))

        # Save all files concurrently
        await asyncio.gather(*file_tasks)

        # Process all files concurrently using the loader
        processing_tasks = []
        valid_files = []  # Track which files are valid for processing

        for i, (temp_path, filename) in enumerate(temp_file_paths):
            # All files should be processed - compression logic is handled in the loader
            # Pass original filename to preserve it in metadata
            processing_tasks.append(
                file_loader.load_file(temp_path, original_filename=filename)
            )
            valid_files.append(
                (temp_path, filename, len(processing_tasks) - 1)
            )  # Store index for mapping

        # Execute all extractions concurrently for valid files only
        if processing_tasks:
            extraction_results = await asyncio.gather(
                *processing_tasks, return_exceptions=True
            )

            # Merge all files' content into single document list
            merged_documents = []
            successful_files = []

            # Process extraction results and convert to standard Document format
            for temp_path, filename, result_index in valid_files:
                try:
                    if isinstance(extraction_results[result_index], Exception):
                        error_msg = str(extraction_results[result_index])
                        logger.error(f"Error processing {filename}: {error_msg}")
                        processed_files.append(
                            {
                                "filename": filename,
                                "status": "error",
                                "error": error_msg,
                            }
                        )
                    else:
                        # Get extracted data and standardize to Document format
                        raw_data = extraction_results[result_index]

                        # Convert all data to standard LangChain Document structure
                        file_documents = []

                        if isinstance(raw_data, str):
                            # Plain text (e.g., audio transcriptions) -> single Document
                            file_documents.append(
                                Document(
                                    page_content=raw_data,
                                    metadata={"source": filename, "original_filename": filename}
                                )
                            )
                        elif isinstance(raw_data, list):
                            # List of items -> convert each to Document
                            for item in raw_data:
                                if isinstance(item, Document):
                                    # Already a Document, just update metadata
                                    if not item.metadata:
                                        item.metadata = {}
                                    item.metadata["original_filename"] = filename
                                    if "source" not in item.metadata:
                                        item.metadata["source"] = filename
                                    file_documents.append(item)
                                elif isinstance(item, dict) and "page_content" in item:
                                    # Dict with page_content -> convert to Document
                                    metadata = item.get("metadata", {})
                                    metadata["original_filename"] = filename
                                    if "source" not in metadata:
                                        metadata["source"] = filename
                                    file_documents.append(
                                        Document(
                                            page_content=item["page_content"],
                                            metadata=metadata
                                        )
                                    )
                                else:
                                    # Any other content -> convert to Document
                                    content = str(item) if not isinstance(item, str) else item
                                    file_documents.append(
                                        Document(
                                            page_content=content,
                                            metadata={"source": filename, "original_filename": filename}
                                        )
                                    )
                        else:
                            # Any other data type -> convert to single Document
                            content = str(raw_data)
                            file_documents.append(
                                Document(
                                    page_content=content,
                                    metadata={"source": filename, "original_filename": filename}
                                )
                            )

                        # Add all documents from this file to merged list
                        merged_documents.extend(file_documents)
                        successful_files.append(filename)
                        processed_files.append(
                            {"filename": filename, "status": "success"}
                        )

                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    processed_files.append(
                        {"filename": filename, "status": "error", "error": str(e)}
                    )

            # Save merged content to database and pgvector if we have successful extractions
            pgvector_status = {"status": "not_attempted", "error": None}
            postgres_status = {"status": "not_attempted", "error": None}

            if merged_documents:

                # Convert Documents to standard dict format for PostgreSQL storage
                documents_data = []
                for doc in merged_documents:
                    doc_dict = {
                        "page_content": doc.page_content,
                        "metadata": doc.metadata
                    }
                    documents_data.append(doc_dict)

                # Store as simple list of Document dictionaries
                content_text = json.dumps(documents_data)

                # Try pgvector insertion first
                if pgvector_collection_name:
                    try:
                        pgvector_status["status"] = "attempting"

                        # Split documents using text splitter
                        text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
                            encoding_name="cl100k_base",
                            chunk_size=settings.CHUNK_SIZE,
                            chunk_overlap=settings.CHUNK_OVERLAP
                        )
                        splitted_docs = text_splitter.split_documents(merged_documents)

                        # Insert chunked documents into pgvector
                        await pg_insertion(
                            splitted_docs,
                            embedder,
                            pgvector_collection_name,
                            user_id=user_id,
                        )
                        pgvector_status = {
                            "status": "success",
                            "collection_name": pgvector_collection_name,
                            "documents_count": len(splitted_docs),
                            "error": None
                        }
                    except Exception as e:
                        pgvector_status = {
                            "status": "failed",
                            "error": str(e),
                            "collection_name": pgvector_collection_name
                        }
                        logger.error(f"Error inserting documents into pgvector: {e}")
                else:
                    pgvector_status["status"] = "skipped_no_collection_name"

                # Try PostgreSQL insertion
                try:
                    postgres_status["status"] = "attempting"

                    # Save single merged entry to knowledge_base table
                    knowledge_entry = KnowledgeBase(
                        tenant_id=final_tenant_id,
                        user_id=user_id,  # Optional user_id - if None, content is shared across tenant
                        content=content_text,
                        pgvector_collection_name=pgvector_collection_name,  # Always store collection name regardless of permissions
                    )

                    db.add(knowledge_entry)
                    total_saved = 1  # Only one merged entry

                    postgres_status = {
                        "status": "success",
                    }

                except Exception as e:
                    postgres_status = {
                        "status": "failed",
                    }
                    logger.error(f"Error saving merged content to database: {str(e)}")
                    # Update all successful files to error status if postgres fails
                    for i, file_info in enumerate(processed_files):
                        if file_info["status"] == "success":
                            processed_files[i] = {
                                "filename": file_info["filename"],
                                "status": "error",
                                "error": f"Database save failed: {str(e)}",
                            }

        # Commit all database changes
        try:
            await db.commit()
        except Exception as e:
            # If commit fails, update postgres status
            logger.error(f"Database commit failed: {str(e)}")
            if postgres_status.get("status") == "success":
                postgres_status = {
                    "status": "failed",
                    "error": f"Database commit failed: {str(e)}"
                }
                # Update file statuses if commit fails
                for i, file_info in enumerate(processed_files):
                    if file_info["status"] == "success":
                        processed_files[i] = {
                            "filename": file_info["filename"],
                            "status": "error",
                            "error": f"Database commit failed: {str(e)}",
                        }
            await db.rollback()

        # Determine overall status based on both insertions
        overall_success = (pgvector_status.get("status") in ["success", "skipped_no_collection_name"] and
                          postgres_status.get("status") == "success")

        response_content = {
            "message": "Successfully processed files" if overall_success else "Files processed with some insertion failures",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "files": processed_files,
            "insertion_status": {
                "pgvector": pgvector_status,
                "postgres": postgres_status,
                "overall_success": overall_success
            },
            "summary": {
                "total_files_processed": len(processed_files),
                "successful_extractions": len(successful_files) if 'successful_files' in locals() else 0,
                "pgvector_inserted": pgvector_status.get("status") == "success",
                "postgres_saved": postgres_status.get("status") == "success"
            }
        }


        return JSONResponse(content=response_content)

    except HTTPException as he:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing files: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to process files: {str(e)}"
        )

    finally:
        # Clean up all temporary files
        for temp_path, filename in temp_file_paths:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(
                        f"Failed to delete temporary file {temp_path}: {str(e)}"
                    )


@content_extractor.get("/get-content")
async def get_content(
    tenant_id: str, user_id: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    """
    Retrieve content by tenant_id and optional user_id

    Args:
        tenant_id: Tenant identifier
        user_id: Optional user identifier (if None, returns all content for tenant)
        db: Database session

    Returns:
        JSON response with content entries
    """
    try:
        # Find tenant by tenant_id (custom identifier)
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.tenant_id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=404, detail=f"Tenant '{tenant_id}' not found"
            )

        # Use the actual UUID for querying knowledge base
        actual_tenant_id = str(tenant.id)

        # Query knowledge base entries
        if user_id:
            query = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.tenant_id == actual_tenant_id,
                    KnowledgeBase.user_id == user_id,
                )
                .order_by(KnowledgeBase.created_at.desc())
            )
        else:
            # Return all content for tenant if user_id is None
            query = (
                select(KnowledgeBase)
                .where(KnowledgeBase.tenant_id == actual_tenant_id)
                .order_by(KnowledgeBase.created_at.desc())
            )

        result = await db.execute(query)
        knowledge_entries = result.scalars().all()

        # Parse content as list of LangChain Documents
        parsed_entries = []
        for entry in knowledge_entries:
            try:
                # Parse JSON content which should be a list of Document dictionaries
                documents = json.loads(entry.content) if entry.content else []

                # Ensure documents is a list
                if not isinstance(documents, list):
                    documents = [documents]

                parsed_entries.append({
                    "id": str(entry.id),
                    "user_id": entry.user_id,
                    "documents": documents,  # List of {page_content: str, metadata: dict}
                    "document_count": len(documents),
                    "pgvector_collection_name": entry.pgvector_collection_name,
                    "created_at": entry.created_at.isoformat(),
                })
            except json.JSONDecodeError:
                # Fallback for non-JSON content
                parsed_entries.append({
                    "id": str(entry.id),
                    "user_id": entry.user_id,
                    "documents": [{"page_content": entry.content, "metadata": {}}],
                    "document_count": 1,
                    "pgvector_collection_name": entry.pgvector_collection_name,
                    "created_at": entry.created_at.isoformat(),
                })

        return JSONResponse(
            content={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "total_entries": len(knowledge_entries),
                "entries": parsed_entries,
            }
        )

    except Exception as e:
        logger.error(f"Error retrieving content: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve content: {str(e)}"
        )


@content_extractor.get("/formats")
async def get_supported_formats():
    """Get list of supported file formats with size limits and compression info"""
    return {
        "supported_formats": [
            ".pdf",
            ".pptx",
            ".docx",
            ".doc",
            ".mp3",
            ".wav",
            ".xlsx",
            ".xls",
            ".csv",
        ],
        "format_descriptions": {
            ".pdf": "PDF documents (max 200MB, auto-compressed for optimization)",
            ".docx": "Microsoft Word documents - new format (max 200MB, auto-compressed for optimization)",
            ".doc": "Microsoft Word documents - legacy format (max 200MB, no compression)",
            ".pptx": "Microsoft PowerPoint presentations (max 200MB, auto-compressed for optimization)",
            ".xlsx": "Microsoft Excel spreadsheets - new format (max 50MB, no compression)",
            ".xls": "Microsoft Excel spreadsheets - legacy format (max 50MB, no compression)",
            ".csv": "Comma-separated values files (max 50MB, no compression)",
            ".mp3": "MP3 audio files - transcription via OpenAI Whisper (max 200MB, no compression)",
            ".wav": "WAV audio files - transcription via OpenAI Whisper (max 200MB, auto-compressed if >100MB)",
        },
        "size_limits": {
            "compressible_document_files": "200MB max (PDF, DOCX, PPTX) - automatically compressed for optimization",
            "doc_files": "200MB max (DOC) - no compression available",
            "excel_csv_files": "50MB max (Excel, CSV) - no compression applied",
            "mp3_files": "200MB max - processed without compression",
            "wav_files": "200MB max - files >100MB automatically compressed to ≤100MB before processing",
            "max_files_per_request": 10,
        },
        "compression_info": {
            "document_compression": "PDF, DOCX, PPTX files are automatically compressed for optimization (no size restrictions)",
            "wav_compression": "WAV files >100MB are automatically compressed to ≤100MB before processing",
            "no_compression": "DOC, MP3, Excel, and CSV files are not compressed",
            "compression_behavior": "Compression is attempted for optimization, original file is used if compression fails",
        },
    }
