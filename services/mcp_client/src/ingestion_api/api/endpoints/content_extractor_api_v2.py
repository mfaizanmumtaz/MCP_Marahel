import os
import tempfile
import asyncio
import json
import time
from typing import List
from pathlib import Path
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

# Document processor
from services.document_processor import DocumentProcessor

# Database
from ingestion_api.db.connection import get_db
from ingestion_api.db.models import KnowledgeBase, Tenant

# RAG vector store
from ingestion_api.utils.pg_vector import pg_insertion
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader

# Settings
from config.settings import settings

logger = logging.getLogger(__name__)

# Create APIRouter
content_extractor_v2 = APIRouter()

# Initialize components
embedder = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL)
doc_processor = DocumentProcessor(gotenberg_url=os.getenv("GOTENBERG_URL", "http://localhost:3000"))


def validate_file_extension(filename: str) -> bool:
    """Validate if file extension is supported"""
    supported_extensions = {".pdf", ".docx", ".doc"}
    file_extension = Path(filename).suffix.lower()
    return file_extension in supported_extensions


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


@content_extractor_v2.post("/extract-files")
async def extract_multiple_files(
    files: List[UploadFile] = File(...),
    tenant_id: str = Form(...),
    summary_access: bool = Form(...),
    translation_access: bool = Form(...),
    rag_access: bool = Form(...),
    cag_access: bool = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Extract text from multiple uploaded PDF/DOCX/DOC files

    Process:
    1. Validate MIME types
    2. For PDFs: Check for images → Compress if >10MB and has images → OCR
    3. For DOCX: Check for images → Convert to PDF if has images → Process as PDF
    4. Generate thumbnails
    5. Store in PostgreSQL and pgvector
    6. Track individual files for deletion

    Args:
        files: List of uploaded files
        tenant_id: Tenant identifier
        summary_access: Enable summary access
        translation_access: Enable translation access
        rag_access: Enable RAG access
        cag_access: Enable CAG access
        db: Database session

    Returns:
        JSON response with detailed processing information
    """
    start_time = time.time()

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per request")

    # Find or create tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            tenant_id=tenant_id,
            summary_access=summary_access,
            translation_access=translation_access,
            rag_access=rag_access,
            cag_access=cag_access,
        )
        db.add(tenant)
        await db.flush()
        logger.info(f"Created new tenant: {tenant_id}")
    else:
        # Update permissions
        tenant.summary_access = summary_access
        tenant.translation_access = translation_access
        tenant.rag_access = rag_access
        tenant.cag_access = cag_access

    # Generate or reuse pgvector collection name
    existing_collection = await db.execute(
        select(KnowledgeBase.pgvector_collection_name)
        .where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.pgvector_collection_name.isnot(None),
        )
        .limit(1)
    )
    pgvector_collection_name = existing_collection.scalar_one_or_none()

    if not pgvector_collection_name:
        import random
        import string
        import datetime
        ts = datetime.datetime.now().strftime("%y%m%d_%H%M")
        rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        pgvector_collection_name = f"pg_collection_{ts}_{rand}_{tenant_id}"

    # Create storage directories
    storage_base = Path("storage") / tenant_id
    thumbnails_dir = storage_base / "thumbnails"
    pdfs_dir = storage_base / "pdfs"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    processed_files = []
    temp_file_paths = []
    all_documents_for_pgvector = []

    try:
        # Validate all files first
        for file in files:
            if not validate_file_extension(file.filename):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{file.filename}'. Only PDF, DOCX, DOC supported.",
                )

        # Save all files to temp locations
        file_tasks = []
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
                temp_file_path = temp_file.name
                temp_file_paths.append((temp_file_path, file.filename))
                file_tasks.append(save_upload_file(file, temp_file_path))

        await asyncio.gather(*file_tasks)

        # Process each file
        for temp_path, filename in temp_file_paths:
            file_start_time = time.time()
            extraction_method = "unknown"
            thumbnail_path = None
            pdf_path = None
            documents = []

            try:
                # Step 1: Validate MIME type
                is_valid_mime, detected_mime = doc_processor.validate_mime_type(temp_path)
                if not is_valid_mime:
                    raise ValueError(f"Invalid MIME type: {detected_mime}")

                file_extension = Path(filename).suffix.lower()
                file_size_mb = doc_processor.get_file_size_mb(temp_path)
                logger.info(f"Processing {filename} ({file_size_mb:.2f}MB, MIME: {detected_mime})")

                # Step 2: Process based on file type
                if file_extension == ".pdf":
                    # PDF processing
                    has_images = doc_processor.check_pdf_has_images(temp_path)

                    pdf_to_process = temp_path

                    # Compress if has images and file size >10MB
                    if has_images and file_size_mb > 10:
                        logger.info(f"PDF has images and file is >10MB ({file_size_mb:.2f}MB), compressing...")
                        compressed_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                        success = await doc_processor.compress_pdf_with_ghostscript(temp_path, compressed_pdf)
                        if success:
                            pdf_to_process = compressed_pdf
                            logger.info(f"PDF compressed successfully")

                    # OCR extraction
                    logger.info(f"Using OCR for PDF extraction...")
                    documents = await doc_processor.process_pdf_with_ocr(
                        pdf_to_process,
                        settings.OPENROUTER_API_KEY,
                        filename
                    )
                    extraction_method = "ocr"

                    # Generate thumbnail
                    thumbnail_filename = f"{Path(filename).stem}_{int(time.time())}.png"
                    thumbnail_path = str(thumbnails_dir / thumbnail_filename)
                    await doc_processor.generate_pdf_thumbnail(pdf_to_process, thumbnail_path)

                    # Save PDF path if compressed
                    if pdf_to_process != temp_path:
                        pdf_filename = f"{Path(filename).stem}_{int(time.time())}.pdf"
                        saved_pdf_path = str(pdfs_dir / pdf_filename)
                        os.rename(pdf_to_process, saved_pdf_path)
                        pdf_path = saved_pdf_path

                elif file_extension in [".docx", ".doc"]:
                    # DOCX/DOC processing
                    if file_extension == ".docx":
                        has_images = doc_processor.check_docx_has_images(temp_path)
                    else:
                        # DOC files - assume might have images
                        has_images = True

                    if has_images:
                        # Convert to PDF using Gotenberg
                        logger.info(f"DOCX/DOC has images, converting to PDF...")
                        converted_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                        success = await doc_processor.convert_docx_to_pdf_gotenberg(temp_path, converted_pdf)

                        if not success:
                            raise ValueError("DOCX to PDF conversion failed")

                        # Check converted PDF file size
                        converted_size_mb = doc_processor.get_file_size_mb(converted_pdf)
                        pdf_to_process = converted_pdf

                        # Compress if converted PDF >10MB
                        if converted_size_mb > 10:
                            logger.info(f"Converted PDF is >10MB ({converted_size_mb:.2f}MB), compressing...")
                            compressed_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                            success = await doc_processor.compress_pdf_with_ghostscript(converted_pdf, compressed_pdf)
                            if success:
                                pdf_to_process = compressed_pdf
                                logger.info(f"Converted PDF compressed successfully")

                        # OCR extraction from converted PDF
                        logger.info(f"Using OCR for converted PDF...")
                        documents = await doc_processor.process_pdf_with_ocr(
                            pdf_to_process,
                            settings.OPENROUTER_API_KEY,
                            filename
                        )
                        extraction_method = "docx_conversion_ocr"

                        # Generate thumbnail from PDF
                        thumbnail_filename = f"{Path(filename).stem}_{int(time.time())}.png"
                        thumbnail_path = str(thumbnails_dir / thumbnail_filename)
                        await doc_processor.generate_pdf_thumbnail(pdf_to_process, thumbnail_path)

                        # Save converted PDF
                        pdf_filename = f"{Path(filename).stem}_{int(time.time())}.pdf"
                        saved_pdf_path = str(pdfs_dir / pdf_filename)
                        os.rename(pdf_to_process, saved_pdf_path)
                        pdf_path = saved_pdf_path

                    else:
                        # No images - use standard text extraction
                        logger.info(f"DOCX has no images, using text extraction...")
                        loader = PyMuPDFLoader(temp_path)
                        documents = await loader.aload()
                        extraction_method = "text_extraction"

                        # Update metadata
                        for doc in documents:
                            doc.metadata["source"] = filename
                            doc.metadata["extraction_method"] = extraction_method

                # Validate documents extracted
                if not documents:
                    raise ValueError("No content extracted from file")

                # Calculate processing time for this file
                file_processing_time = time.time() - file_start_time

                # Convert documents to JSON format for PostgreSQL
                documents_data = []
                for doc in documents:
                    doc_dict = {
                        "page_content": doc.page_content,
                        "metadata": doc.metadata
                    }
                    documents_data.append(doc_dict)

                # Store in PostgreSQL
                knowledge_entry = KnowledgeBase(
                    tenant_id=tenant_id,
                    filename=filename,
                    file_type=file_extension.replace(".", ""),
                    file_size_mb=f"{file_size_mb:.2f}",
                    extraction_method=extraction_method,
                    processing_time_seconds=f"{file_processing_time:.2f}",
                    content=json.dumps(documents_data),
                    thumbnail_path=thumbnail_path,
                    pdf_path=pdf_path,
                    pgvector_collection_name=pgvector_collection_name,
                    page_count=str(len(documents)),
                )
                db.add(knowledge_entry)

                # Add to pgvector batch
                all_documents_for_pgvector.extend(documents)

                # Track success
                processed_files.append({
                    "filename": filename,
                    "status": "success",
                    "extraction_method": extraction_method,
                    "page_count": len(documents),
                    "processing_time_seconds": f"{file_processing_time:.2f}",
                    "file_size_mb": f"{file_size_mb:.2f}",
                    "has_thumbnail": thumbnail_path is not None,
                })

                logger.info(f"Successfully processed {filename} using {extraction_method}")

            except Exception as e:
                logger.error(f"Error processing {filename}: {str(e)}")
                processed_files.append({
                    "filename": filename,
                    "status": "error",
                    "error": str(e),
                })

        # Insert all documents into pgvector
        pgvector_status = {"status": "not_attempted", "error": None}
        if all_documents_for_pgvector:
            try:
                # Split documents using text splitter
                text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
                    encoding_name="cl100k_base",
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP
                )
                splitted_docs = text_splitter.split_documents(all_documents_for_pgvector)

                # Insert into pgvector
                await pg_insertion(
                    splitted_docs,
                    embedder,
                    pgvector_collection_name,
                )
                pgvector_status = {
                    "status": "success",
                    "collection_name": pgvector_collection_name,
                    "documents_count": len(splitted_docs),
                }
            except Exception as e:
                pgvector_status = {
                    "status": "failed",
                    "error": str(e),
                }
                logger.error(f"Error inserting into pgvector: {e}")

        # Commit database changes
        try:
            await db.commit()
            postgres_status = {"status": "success"}
        except Exception as e:
            await db.rollback()
            postgres_status = {"status": "failed", "error": str(e)}
            logger.error(f"Database commit failed: {e}")

        # Calculate total processing time
        total_time = time.time() - start_time

        # Prepare response
        successful_files = [f for f in processed_files if f["status"] == "success"]
        failed_files = [f for f in processed_files if f["status"] == "error"]

        # Group by extraction method
        extraction_methods = {}
        for f in successful_files:
            method = f.get("extraction_method", "unknown")
            extraction_methods[method] = extraction_methods.get(method, 0) + 1

        response = {
            "message": f"Processed {len(successful_files)}/{len(processed_files)} files successfully",
            "tenant_id": tenant_id,
            "processing_time_seconds": f"{total_time:.2f}",
            "files": processed_files,
            "summary": {
                "total_files": len(processed_files),
                "successful": len(successful_files),
                "failed": len(failed_files),
                "extraction_methods_used": extraction_methods,
                "total_pages": sum(f.get("page_count", 0) for f in successful_files),
            },
            "storage": {
                "postgres": postgres_status,
                "pgvector": pgvector_status,
            },
        }

        return JSONResponse(content=response)

    except HTTPException as he:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process files: {str(e)}")

    finally:
        # Clean up temporary files
        for temp_path, filename in temp_file_paths:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_path}: {str(e)}")


@content_extractor_v2.get("/documents")
async def get_tenant_documents(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all documents uploaded by a tenant

    Args:
        tenant_id: Tenant identifier
        db: Database session

    Returns:
        JSON response with all documents
    """
    try:
        # Verify tenant exists
        tenant_result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")

        # Get all documents for tenant
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        documents = result.scalars().all()

        # Format response with download URLs
        documents_list = []
        for doc in documents:
            doc_data = {
                "id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size_mb": doc.file_size_mb,
                "extraction_method": doc.extraction_method,
                "processing_time_seconds": doc.processing_time_seconds,
                "page_count": doc.page_count,
                "created_at": doc.created_at.isoformat(),
                "thumbnail_url": None,
                "pdf_url": None,
            }

            # Add thumbnail URL if exists
            if doc.thumbnail_path and os.path.exists(doc.thumbnail_path):
                doc_data["thumbnail_url"] = f"/api/content-extractor-v2/documents/{doc.id}/thumbnail?tenant_id={tenant_id}"

            # Add PDF URL if exists
            if doc.pdf_path and os.path.exists(doc.pdf_path):
                doc_data["pdf_url"] = f"/api/content-extractor-v2/documents/{doc.id}/pdf?tenant_id={tenant_id}"

            documents_list.append(doc_data)

        return JSONResponse(content={
            "tenant_id": tenant_id,
            "total_documents": len(documents_list),
            "documents": documents_list,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")


@content_extractor_v2.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a specific document

    Args:
        document_id: Document UUID
        tenant_id: Tenant identifier
        db: Database session

    Returns:
        JSON response with deletion status
    """
    try:
        # Find document
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == document_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document_id}' not found for tenant '{tenant_id}'"
            )

        # Delete physical files
        files_deleted = []
        if document.thumbnail_path and os.path.exists(document.thumbnail_path):
            os.unlink(document.thumbnail_path)
            files_deleted.append("thumbnail")

        if document.pdf_path and os.path.exists(document.pdf_path):
            os.unlink(document.pdf_path)
            files_deleted.append("pdf")

        # Delete from database
        await db.delete(document)
        await db.commit()

        logger.info(f"Deleted document {document_id} for tenant {tenant_id}")

        return JSONResponse(content={
            "message": "Document deleted successfully",
            "document_id": document_id,
            "filename": document.filename,
            "files_deleted": files_deleted,
        })

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@content_extractor_v2.get("/documents/{document_id}/pdf")
async def get_document_pdf(
    document_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Download or view the converted PDF file for a document

    Args:
        document_id: Document UUID
        tenant_id: Tenant identifier
        db: Database session

    Returns:
        PDF file as FileResponse
    """
    try:
        # Find document and verify ownership
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == document_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document_id}' not found for tenant '{tenant_id}'"
            )

        # Check if PDF exists
        if not document.pdf_path:
            raise HTTPException(
                status_code=404,
                detail=f"PDF not available for this document (original file type: {document.file_type})"
            )

        if not os.path.exists(document.pdf_path):
            raise HTTPException(
                status_code=404,
                detail="PDF file not found on server"
            )

        # Serve PDF file
        return FileResponse(
            path=document.pdf_path,
            media_type="application/pdf",
            filename=f"{Path(document.filename).stem}.pdf",
            headers={
                "Content-Disposition": f'inline; filename="{Path(document.filename).stem}.pdf"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve PDF: {str(e)}")


@content_extractor_v2.get("/documents/{document_id}/thumbnail")
async def get_document_thumbnail(
    document_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the thumbnail image for a document

    Args:
        document_id: Document UUID
        tenant_id: Tenant identifier
        db: Database session

    Returns:
        Thumbnail image as FileResponse
    """
    try:
        # Find document and verify ownership
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == document_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document_id}' not found for tenant '{tenant_id}'"
            )

        # Check if thumbnail exists
        if not document.thumbnail_path:
            raise HTTPException(
                status_code=404,
                detail="Thumbnail not available for this document"
            )

        if not os.path.exists(document.thumbnail_path):
            raise HTTPException(
                status_code=404,
                detail="Thumbnail file not found on server"
            )

        # Serve thumbnail image
        return FileResponse(
            path=document.thumbnail_path,
            media_type="image/png",
            filename=f"{Path(document.filename).stem}_thumbnail.png"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve thumbnail: {str(e)}")


@content_extractor_v2.get("/formats")
async def get_supported_formats():
    """Get list of supported file formats"""
    return {
        "supported_formats": [".pdf", ".docx", ".doc"],
        "format_descriptions": {
            ".pdf": "PDF documents - OCR extraction with table/image preservation",
            ".docx": "Microsoft Word documents - Text extraction or conversion to PDF",
            ".doc": "Microsoft Word legacy - Text extraction or conversion to PDF",
        },
        "features": {
            "mime_type_validation": True,
            "image_detection": True,
            "automatic_compression": True,
            "thumbnail_generation": True,
            "table_preservation": True,
            "ocr_support": True,
            "pdf_download": True,
            "thumbnail_preview": True,
        },
    }
