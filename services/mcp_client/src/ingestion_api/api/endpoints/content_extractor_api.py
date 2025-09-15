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
from ingestion_api.db.postgres_connection import get_db
from ingestion_api.db.user_db import KnowledgeBase, Tenant
from sqlalchemy import select

# RAG vector store imports
from ingestion_api.utils.pg_vector import pg_insertion
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import random

import string
import datetime

# Set up logging
log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)
handler = logging.FileHandler(os.path.join(log_dir, "content_extractor_api.log"))
handler.setFormatter(formatter)
logger.addHandler(handler)

# Create APIRouter instance
content_extractor = APIRouter()

# Initialize RAG components
embedder = OpenAIEmbeddings(model="text-embedding-3-small")

# Global loader instance (will be initialized in main.py)
loader: Optional[UniversalFileLoader] = None


async def get_loader() -> UniversalFileLoader:
    """Dependency to get the loader instance"""
    global loader
    if loader is None:
        # Initialize loader if not already done
        loader = UniversalFileLoader()
        logger.info("Loader initialized in dependency")
    return loader


async def copy_existing_data_to_pgvector(
    db: AsyncSession,
    tenant_id: str,
    user_id: Optional[str],
    pgvector_collection_name: str,
) -> int:
    """
    Copy existing knowledge_base data to pgvector when rag_access changes from false to true

    Args:
        db: Database session
        tenant_id: Tenant UUID
        user_id: Optional user ID
        pgvector_collection_name: Name of the pgvector collection to use

    Returns:
        Number of entries copied to pgvector
    """
    try:
        # Query existing knowledge_base entries that don't have pgvector collection name
        if user_id:
            query = select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.pgvector_collection_name.is_(
                    None
                ),  # Only entries without vector collection
            )
        else:
            query = select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.pgvector_collection_name.is_(
                    None
                ),  # Only entries without vector collection
            )

        result = await db.execute(query)
        existing_entries = result.scalars().all()

        if not existing_entries:
            logger.info("No existing entries found to copy to pgvector")
            return 0

        # Process each existing entry
        copied_count = 0
        all_documents = []
        entry_ids = []

        for entry in existing_entries:
            try:
                # Parse the stored JSON content
                if entry.content.startswith("[") or entry.content.startswith("{"):
                    content_data = json.loads(entry.content)
                else:
                    # Plain text content
                    content_data = entry.content

                # Convert to Document objects
                documents = []
                if isinstance(content_data, list):
                    for item in content_data:
                        if isinstance(item, dict):
                            if "page_content" in item:
                                metadata = item.get("metadata", {})
                                documents.append(
                                    Document(
                                        page_content=item["page_content"],
                                        metadata=metadata,
                                    )
                                )
                            else:
                                # Handle other dict formats
                                page_content = str(item)
                                documents.append(
                                    Document(
                                        page_content=page_content,
                                        metadata={"entry_id": str(entry.id)},
                                    )
                                )
                        else:
                            # Handle string or other types
                            page_content = str(item)
                            documents.append(
                                Document(
                                    page_content=page_content,
                                    metadata={"entry_id": str(entry.id)},
                                )
                            )
                elif isinstance(content_data, str):
                    # Plain text content
                    documents.append(
                        Document(
                            page_content=content_data,
                            metadata={"entry_id": str(entry.id)},
                        )
                    )

                if documents:
                    all_documents.extend(documents)
                    entry_ids.append(entry.id)
                    copied_count += 1

            except Exception as e:
                logger.error(f"Error processing existing entry {entry.id}: {str(e)}")
                continue

        # Insert all documents into pgvector if we have any
        if all_documents:
            try:
                await pg_insertion(
                    all_documents, embedder, pgvector_collection_name, user_id
                )
                logger.info(
                    f"Successfully copied {len(all_documents)} documents from {copied_count} entries to pgvector: {pgvector_collection_name}"
                )

                # Update the existing entries with the pgvector collection name
                for entry_id in entry_ids:
                    await db.execute(
                        select(KnowledgeBase).where(KnowledgeBase.id == entry_id)
                    )
                    entry_to_update = await db.get(KnowledgeBase, entry_id)
                    if entry_to_update:
                        entry_to_update.pgvector_collection_name = (
                            pgvector_collection_name
                        )

                await db.commit()
                logger.info(
                    f"Updated {len(entry_ids)} existing entries with pgvector collection name"
                )

            except Exception as e:
                logger.error(f"Error inserting existing data into pgvector: {str(e)}")
                await db.rollback()
                return 0

        return copied_count

    except Exception as e:
        logger.error(f"Error copying existing data to pgvector: {str(e)}")
        return 0


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
        files: List of uploaded files
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
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

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
        logger.info(
            f"Created new tenant: tenant_id='{tenant_id}', user_id='{user_id}', UUID={tenant.id}"
        )
    else:
        # Existing tenant - check if permissions need updating
        original_rag_access = tenant.rag_access
        permissions_updated = False
        changes_made = []

        # Update permissions if they differ from current values
        if tenant.summary_access != summary_access:
            tenant.summary_access = summary_access
            permissions_updated = True
            changes_made.append(
                f"summary_access: {tenant.summary_access} -> {summary_access}"
            )

        if tenant.translation_access != translation_access:
            tenant.translation_access = translation_access
            permissions_updated = True
            changes_made.append(
                f"translation_access: {tenant.translation_access} -> {translation_access}"
            )

        if tenant.rag_access != rag_access:
            tenant.rag_access = rag_access
            permissions_updated = True
            changes_made.append(f"rag_access: {original_rag_access} -> {rag_access}")

        if tenant.cag_access != cag_access:
            tenant.cag_access = cag_access
            permissions_updated = True
            changes_made.append(f"cag_access: {tenant.cag_access} -> {cag_access}")

        if permissions_updated:
            logger.info(
                f"Updated existing tenant permissions: tenant_id='{tenant_id}', changes: {changes_made}"
            )
        else:
            logger.info(
                f"Using existing tenant: tenant_id='{tenant_id}', no permission changes needed"
            )

    # Use the actual UUID for foreign key
    final_tenant_id = str(tenant.id)

    # Determine pgvector collection name - always create regardless of cag_access
    pgvector_collection_name = None
    copied_existing_data = False

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
        logger.info(f"Reusing existing collection: {pgvector_collection_name}")
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
        logger.info(f"Created new collection: {pgvector_collection_name}")

        # Check if this is an existing tenant case
        if "tenant" in locals() and hasattr(tenant, "id"):  # Existing tenant case
            # Copy existing data from knowledge_base to pgvector
            logger.info("Checking for existing data to copy to pgvector...")
            copied_count = await copy_existing_data_to_pgvector(
                db, final_tenant_id, user_id, pgvector_collection_name
            )
            if copied_count > 0:
                copied_existing_data = True
                logger.info(
                    f"Successfully copied {copied_count} existing entries to pgvector"
                )

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
        logger.info(
            f"Successfully saved {len(file_tasks)} files to temporary locations"
        )

        # Process all files concurrently using the loader
        processing_tasks = []
        valid_files = []  # Track which files are valid for processing

        for temp_path, filename in temp_file_paths:
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

            # Process extraction results and merge into single list
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
                        # Get extracted data
                        raw_data = extraction_results[result_index]

                        # Convert plain text to Document objects for consistency
                        if isinstance(raw_data, str):
                            # Plain text (audio transcriptions) -> convert to Document object
                            raw_data = [
                                Document(
                                    page_content=raw_data, metadata={"source": filename}
                                )
                            ]

                        # Add all documents from this file to merged list
                        if isinstance(raw_data, list):
                            for item in raw_data:
                                if hasattr(item, "page_content"):
                                    merged_documents.append(item)
                                elif isinstance(item, dict) and "page_content" in item:
                                    # Convert dict to Document if it has page_content
                                    metadata = item.get("metadata", {})
                                    merged_documents.append(
                                        Document(
                                            page_content=item["page_content"],
                                            metadata=metadata,
                                        )
                                    )
                                else:
                                    # Create Document from string/other content
                                    content = (
                                        str(item) if not isinstance(item, str) else item
                                    )
                                    merged_documents.append(
                                        Document(
                                            page_content=content,
                                            metadata={"source": filename},
                                        )
                                    )

                        successful_files.append(filename)
                        processed_files.append(
                            {"filename": filename, "status": "success"}
                        )
                        logger.info(f"Successfully processed {filename}")

                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    processed_files.append(
                        {"filename": filename, "status": "error", "error": str(e)}
                    )

            # Save merged content to database and pgvector if we have successful extractions
            if merged_documents:
                try:
                    # Store merged content as JSON string
                    content_text = json.dumps(
                        [
                            doc.__dict__ if hasattr(doc, "__dict__") else str(doc)
                            for doc in merged_documents
                        ]
                    )

                    # RAG processing: send merged documents to pgvector regardless of cag_access
                    if pgvector_collection_name:
                        try:
                            # Insert all merged documents into pgvector
                            await pg_insertion(
                                merged_documents,
                                embedder,
                                pgvector_collection_name,
                                user_id=user_id,
                            )
                            logger.info(
                                f"Successfully inserted {len(merged_documents)} merged documents from {len(successful_files)} files into pgvector: {pgvector_collection_name}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error inserting merged documents into pgvector: {e}"
                            )

                    # Save single merged entry to knowledge_base table
                    knowledge_entry = KnowledgeBase(
                        tenant_id=final_tenant_id,
                        user_id=user_id,  # Optional user_id - if None, content is shared across tenant
                        content=content_text,
                        pgvector_collection_name=pgvector_collection_name,  # Always store collection name
                    )

                    db.add(knowledge_entry)
                    total_saved = 1  # Only one merged entry

                    logger.info(
                        f"Successfully saved merged content from {len(successful_files)} files to knowledge_base with collection: {pgvector_collection_name}"
                    )

                except Exception as e:
                    logger.error(f"Error saving merged content to database: {str(e)}")
                    # Update all successful files to error status
                    for i, file_info in enumerate(processed_files):
                        if file_info["status"] == "success":
                            processed_files[i] = {
                                "filename": file_info["filename"],
                                "status": "error",
                                "error": f"Database save failed: {str(e)}",
                            }

        # Commit all database changes
        await db.commit()

        logger.info(
            f"Successfully processed {len(processed_files)} files, saved {total_saved} to database"
        )

        response_content = {
            "message": "Successfully processed files",
            # "total_files": len(processed_files),
            # "saved_to_db": total_saved,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "files": processed_files,
        }

        # Add information about copied existing data if applicable
        if copied_existing_data:
            response_content["existing_data_copied"] = True
            response_content["message"] += " and copied existing data to pgvector"

        return JSONResponse(content=response_content)

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing files: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process files: {str(e)}"
        )

    finally:
        # Clean up all temporary files
        for temp_path, filename in temp_file_paths:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Deleted temporary file: {temp_path}")
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

        return JSONResponse(
            content={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "total_entries": len(knowledge_entries),
                "entries": [
                    {
                        "id": str(entry.id),
                        "user_id": entry.user_id,
                        "content": json.loads(entry.content)
                        if entry.content.startswith("[")
                        or entry.content.startswith("{")
                        else entry.content,
                        "pgvector_collection_name": entry.pgvector_collection_name,
                        "created_at": entry.created_at.isoformat(),
                    }
                    for entry in knowledge_entries
                ],
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
