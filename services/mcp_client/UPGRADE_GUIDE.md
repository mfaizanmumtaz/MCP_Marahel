# Content Extractor V2 - Upgrade Guide

## Overview

The Content Extractor V2 API is a complete rewrite of the document ingestion pipeline with enhanced capabilities:

- **MIME type validation** for uploaded files
- **Intelligent image detection** for PDFs and DOCX files
- **Automatic compression** for large files with images (>10MB)
- **OCR extraction** with table and image preservation (Gemini 2.5 Flash)
- **DOCX to PDF conversion** using Gotenberg
- **Thumbnail generation** for all processed documents
- **Individual file tracking** for selective deletion
- **Processing time tracking** and detailed metrics
- **Removed user_id** - tenant-level isolation only

---

## Database Migration

### New Schema Fields

The `knowledge_base` table has been updated with new fields:

```python
class KnowledgeBase(Base):
    id = UUID                          # Document ID
    tenant_id = String(255)            # Foreign key to tenants
    filename = String(500)             # Original filename
    file_type = String(50)             # pdf, docx, doc
    file_size_mb = String(50)          # Original file size
    extraction_method = String(100)    # ocr, text_extraction, docx_conversion_ocr
    processing_time_seconds = String(50)  # Processing time
    content = Text                     # JSON array of documents
    thumbnail_path = String(500)       # Path to thumbnail
    pdf_path = String(500)             # Path to converted PDF (for DOCX)
    pgvector_collection_name = String(255)  # Collection name
    page_count = String(50)            # Number of pages
    created_at = DateTime              # Creation timestamp
```

### Migration Steps

1. **Backup your database:**
   ```bash
   pg_dump -h localhost -U your_user -d your_db > backup_$(date +%Y%m%d).sql
   ```

2. **Run migration:**
   ```bash
   cd services/mcp_client/src
   python -m ingestion_api.db.models
   ```

   Or using Alembic (recommended):
   ```bash
   alembic revision --autogenerate -m "Add V2 schema fields"
   alembic upgrade head
   ```

---

## New Dependencies

Add these to your `requirements.txt`:

```txt
python-magic==0.4.27        # MIME type detection
python-magic-bin==0.4.14    # Windows binary for python-magic
requests==2.31.0            # HTTP requests for Gotenberg
PyMuPDF==1.23.8             # PDF processing and thumbnails
```

Install:
```bash
pip install python-magic python-magic-bin requests PyMuPDF
```

---

## Gotenberg Setup

Gotenberg is required for DOCX to PDF conversion.

### Using Docker:

```bash
docker run -d \
  --name gotenberg \
  -p 3000:3000 \
  gotenberg/gotenberg:8
```

### Using Docker Compose:

Add to your `docker-compose.yml`:

```yaml
services:
  gotenberg:
    image: gotenberg/gotenberg:8
    ports:
      - "3000:3000"
    restart: unless-stopped
```

### Environment Variable:

```bash
export GOTENBERG_URL=http://localhost:3000
```

Or add to your `.env`:
```
GOTENBERG_URL=http://localhost:3000
```

---

## API Changes

### Endpoints

#### V2 Endpoints (New):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/content-extractor-v2/extract-files` | POST | Upload and process files |
| `/api/content-extractor-v2/documents?tenant_id=X` | GET | View all documents for tenant |
| `/api/content-extractor-v2/documents/{doc_id}?tenant_id=X` | DELETE | Delete specific document |
| `/api/content-extractor-v2/formats` | GET | Get supported formats |

#### V1 Endpoints (Legacy - Deprecated):

- `/api/extract-files` - Still available but deprecated
- `/api/get-content` - Still available but deprecated

### Request Changes

**V1 (Old):**
```bash
curl -X POST "http://localhost:8000/api/extract-files" \
  -F "files=@document.pdf" \
  -F "tenant_id=tenant123" \
  -F "user_id=user456" \           # ❌ Removed in V2
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"
```

**V2 (New):**
```bash
curl -X POST "http://localhost:8000/api/content-extractor-v2/extract-files" \
  -F "files=@document.pdf" \
  -F "tenant_id=tenant123" \       # No user_id
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"
```

### Response Format

**V2 Response:**
```json
{
  "message": "Processed 2/2 files successfully",
  "tenant_id": "tenant123",
  "processing_time_seconds": "45.32",
  "files": [
    {
      "filename": "report.pdf",
      "status": "success",
      "extraction_method": "ocr",
      "page_count": 15,
      "processing_time_seconds": "23.45",
      "file_size_mb": "12.34",
      "has_thumbnail": true
    },
    {
      "filename": "document.docx",
      "status": "success",
      "extraction_method": "docx_conversion_ocr",
      "page_count": 8,
      "processing_time_seconds": "21.87",
      "file_size_mb": "8.92",
      "has_thumbnail": true
    }
  ],
  "summary": {
    "total_files": 2,
    "successful": 2,
    "failed": 0,
    "extraction_methods_used": {
      "ocr": 1,
      "docx_conversion_ocr": 1
    },
    "total_pages": 23
  },
  "storage": {
    "postgres": {"status": "success"},
    "pgvector": {
      "status": "success",
      "collection_name": "pg_collection_250102_1234_abcdef_tenant123",
      "documents_count": 46
    }
  }
}
```

---

## Processing Logic

### PDF Files

```
1. Validate MIME type (application/pdf)
2. Check for images using PyMuPDF
   ├─ Has images + >10MB
   │  ├─ Compress with Ghostscript
   │  └─ Process compressed PDF
   └─ Process original PDF
3. Extract with OCR (Gemini 2.5 Flash)
   - Preserves tables in markdown format
   - Preserves image descriptions
   - Maintains text formatting
4. Generate thumbnail (first page)
5. Store in PostgreSQL + pgvector
```

### DOCX Files

```
1. Validate MIME type (application/vnd.openxmlformats-...)
2. Parse XML to check for images
   ├─ Has images
   │  ├─ Convert to PDF (Gotenberg)
   │  ├─ Check converted PDF size
   │  │  └─ If >10MB: Compress with Ghostscript
   │  ├─ Extract with OCR
   │  ├─ Generate thumbnail
   │  └─ Save converted PDF
   └─ No images
      └─ Extract text with PyMuPDFLoader
3. Store in PostgreSQL + pgvector
```

### DOC Files

```
1. Validate MIME type (application/msword)
2. Assume may have images
3. Convert to PDF (Gotenberg)
4. Process as PDF (same as DOCX with images)
```

---

## File Storage Structure

```
storage/
└── {tenant_id}/
    ├── thumbnails/
    │   ├── report_1704123456.png
    │   └── document_1704123789.png
    └── pdfs/
        └── document_1704123789.pdf  (converted DOCX)
```

---

## View Documents API

Get all documents for a tenant:

```bash
curl "http://localhost:8000/api/content-extractor-v2/documents?tenant_id=tenant123"
```

Response:
```json
{
  "tenant_id": "tenant123",
  "total_documents": 5,
  "documents": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "filename": "report.pdf",
      "file_type": "pdf",
      "file_size_mb": "12.34",
      "extraction_method": "ocr",
      "processing_time_seconds": "23.45",
      "page_count": "15",
      "thumbnail_path": "storage/tenant123/thumbnails/report_1704123456.png",
      "pdf_path": null,
      "created_at": "2025-01-02T10:30:00"
    }
  ]
}
```

---

## Delete Document API

Delete a specific document:

```bash
curl -X DELETE \
  "http://localhost:8000/api/content-extractor-v2/documents/123e4567-e89b-12d3-a456-426614174000?tenant_id=tenant123"
```

Response:
```json
{
  "message": "Document deleted successfully",
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "report.pdf",
  "files_deleted": ["thumbnail", "pdf"]
}
```

**Note:** This only deletes the document from PostgreSQL. pgvector embeddings remain in the collection (by design for performance).

---

## Extraction Methods

| Method | Description | When Used |
|--------|-------------|-----------|
| `ocr` | OCR extraction with Gemini 2.5 Flash | PDFs (all cases in V2) |
| `text_extraction` | PyMuPDF text extraction | DOCX without images |
| `docx_conversion_ocr` | DOCX → PDF → OCR | DOCX with images |

---

## Markdown Format

All OCR extractions return content in markdown format:

- **Tables:** Pipe-separated markdown tables
- **Images:** `![Description](Location)` format
- **Formatting:** Bold, italic, headings preserved
- **Structure:** Paragraphs, lists, code blocks maintained

Example:
```markdown
# Section Title

**Important:** This is bold text.

| Column 1 | Column 2 |
|----------|----------|
| Data A   | Data B   |

![Chart showing sales data](Image on page 3)
```

---

## Environment Variables

Required:
```bash
OPENROUTER_API_KEY=your_openrouter_key   # For OCR
OPENAI_API_KEY=your_openai_key          # For embeddings
GOTENBERG_URL=http://localhost:3000     # For DOCX conversion
```

---

## Testing

### Test PDF with Images:
```bash
curl -X POST "http://localhost:8000/api/content-extractor-v2/extract-files" \
  -F "files=@test_with_images.pdf" \
  -F "tenant_id=test_tenant" \
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"
```

### Test DOCX with Images:
```bash
curl -X POST "http://localhost:8000/api/content-extractor-v2/extract-files" \
  -F "files=@document_with_images.docx" \
  -F "tenant_id=test_tenant" \
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"
```

### View Documents:
```bash
curl "http://localhost:8000/api/content-extractor-v2/documents?tenant_id=test_tenant"
```

### Delete Document:
```bash
curl -X DELETE \
  "http://localhost:8000/api/content-extractor-v2/documents/{document_id}?tenant_id=test_tenant"
```

---

## Troubleshooting

### Issue: "Invalid MIME type" error

**Cause:** File MIME type doesn't match PDF/DOCX/DOC
**Solution:** Ensure file is not corrupted and has correct extension

### Issue: "Gotenberg conversion failed"

**Cause:** Gotenberg service not running
**Solution:**
```bash
docker ps | grep gotenberg
docker start gotenberg  # if stopped
docker run -d -p 3000:3000 gotenberg/gotenberg:8  # if not exists
```

### Issue: Thumbnails not generated

**Cause:** PyMuPDF not installed or PDF has no pages
**Solution:**
```bash
pip install PyMuPDF==1.23.8
```

### Issue: OCR returning incomplete content

**Cause:** OpenRouter API rate limits or errors
**Solution:** Check logs for specific error, verify OPENROUTER_API_KEY

---

## Performance Considerations

### V2 Processing Times:

| File Type | Size | Images | Method | Time |
|-----------|------|--------|--------|------|
| PDF | 5MB | No | OCR | ~15s |
| PDF | 15MB | Yes | Compress + OCR | ~30s |
| DOCX | 3MB | No | Text Extract | ~5s |
| DOCX | 10MB | Yes | Convert + OCR | ~25s |

### Optimization Tips:

1. **Batch uploads:** Upload multiple files in one request (up to 10)
2. **Pre-compress:** Compress files before upload if possible
3. **Monitor Gotenberg:** Ensure adequate resources for conversions
4. **pgvector indexing:** Create indexes on frequently queried collections

---

## Migration Checklist

- [ ] Install new dependencies (`python-magic`, `PyMuPDF`)
- [ ] Set up Gotenberg (Docker)
- [ ] Run database migration
- [ ] Set environment variables (`GOTENBERG_URL`)
- [ ] Create storage directories (`storage/{tenant_id}/thumbnails`, `storage/{tenant_id}/pdfs`)
- [ ] Test V2 API with sample files
- [ ] Update client applications to use V2 endpoints
- [ ] Remove `user_id` from API calls
- [ ] Update monitoring/logging for new extraction methods

---

## Support

For issues or questions:
- Check logs in `log/ai/` directory
- Review FastAPI docs at `http://localhost:8000/docs`
- Verify Gotenberg is running: `curl http://localhost:3000/health`
