# Document Processing Flow - Visual Guide

## Complete Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FILE UPLOAD (Multiple Files)                       │
│                  PDF, DOCX, DOC (up to 10 files per request)                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STEP 1: MIME VALIDATION                            │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │  Python      │───▶│  Detect MIME │───▶│  Validate    │                 │
│  │  Magic       │    │  Type        │    │  Type        │                 │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                 │
│                                                   │                          │
│                                    Valid? ────────┤                          │
│                                          Yes      │ No                       │
│                                          │        └──▶ Reject (400 Error)   │
└──────────────────────────────────────────┼──────────────────────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────┐
                          │      FILE TYPE ROUTING          │
                          └──┬──────────────┬───────────┬───┘
                             │              │           │
                 ┌───────────▼───┐  ┌───────▼─────┐   ▼
                 │     PDF       │  │   DOCX      │  DOC
                 └───────┬───────┘  └──────┬──────┘   │
                         │                 │          │
                         │                 │          └──▶ (Same as DOCX)
                         │                 │
        ┌────────────────┴─────────────────┴───────────────┐
        │                                                   │
        ▼                                                   ▼

┌────────────────────────────┐                  ┌─────────────────────────────┐
│    PDF PROCESSING PATH     │                  │   DOCX PROCESSING PATH      │
└────────────────────────────┘                  └─────────────────────────────┘

        │                                                   │
        ▼                                                   ▼
┌───────────────────┐                          ┌────────────────────────┐
│ Image Detection   │                          │  Parse XML Content     │
│ (PyMuPDF)         │                          │  Check word/media/     │
│                   │                          │  Count <pic:pic>       │
│ Returns:          │                          │                        │
│ - has_images      │                          │  Returns:              │
│ - image_count     │                          │  - has_images          │
│ - image_size_mb   │                          │  - image_count         │
└─────────┬─────────┘                          └──────────┬─────────────┘
          │                                               │
          ▼                                               ▼
    Has images?                                     Has images?
          │                                               │
    ┌─────┴─────┐                                   ┌─────┴─────┐
    │ Yes  │ No │                                   │ Yes  │ No │
    │      │    │                                   │      │    │
    ▼      │    │                                   ▼      │    │
┌────────┐ │    │                          ┌──────────────┐│    │
│Size >  │ │    │                          │  Convert to  ││    │
│10MB?   │ │    │                          │  PDF via     ││    │
└───┬────┘ │    │                          │  Gotenberg   ││    │
    │      │    │                          └───────┬──────┘│    │
Yes │ No   │    │                                  │       │    │
    │   │  │    │                                  ▼       │    │
    ▼   │  │    │                          ┌───────────────┤    │
┌─────────┐│    │                          │ Converted     │    │
│Compress ││    │                          │ PDF >10MB?    │    │
│with GS  ││    │                          └───┬───────────┘    │
└────┬────┘│    │                              │                │
     │     │    │                          Yes │ No             │
     ▼     │    │                              │ │              │
┌────────────────┐                             ▼ │              │
│  OCR Extract   │                       ┌──────────┐           │
│  Gemini 2.5    │◀──────────────────────│Compress  │           │
│  Flash         │                       │with GS   │           │
│                │                       └────┬─────┘           │
│  - Tables      │                            │                 │
│  - Images      │                            ▼                 │
│  - Formatting  │                       ┌──────────┐           │
└────────┬───────┘                       │   OCR    │           │
         │                               │ Extract  │           │
         │                               └────┬─────┘           │
         │                                    │                 │
         ▼                                    ▼                 ▼
┌────────────────┐                  ┌─────────────────────────────┐
│  Generate      │                  │  Generate Thumbnail         │
│  Thumbnail     │                  │  from PDF                   │
│  (1st page)    │                  └──────────┬──────────────────┘
└────────┬───────┘                             │
         │                                     │
         │                                     ▼
         │                          ┌──────────────────────┐
         │                          │  Save Converted PDF  │
         │                          │  to storage/         │
         │                          └──────────┬───────────┘
         │                                     │
         ▼                                     ▼
┌────────────────────────────────────────────────────────────┐
│              STANDARDIZE TO DOCUMENT FORMAT                │
│                                                            │
│  Document(                                                 │
│    page_content: "markdown text...",                      │
│    metadata: {                                            │
│      "page": 1,                                           │
│      "source": "filename.pdf",                           │
│      "extraction_method": "ocr"                          │
│    }                                                      │
│  )                                                        │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  TEXT SPLITTING      │
              │  (CharacterSplitter) │
              │                      │
              │  Chunk: 800 chars    │
              │  Overlap: 300 chars  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  EMBEDDING           │
              │  (OpenAI)            │
              │                      │
              │  Model:              │
              │  text-embedding-     │
              │  3-small             │
              └──────────┬───────────┘
                         │
                         ▼
         ┌───────────────┴────────────────┐
         │                                │
         ▼                                ▼
┌─────────────────┐            ┌──────────────────┐
│   PostgreSQL    │            │    pgvector      │
│   Storage       │            │    Storage       │
│                 │            │                  │
│  - Full docs    │            │  - Chunked docs  │
│  - Metadata     │            │  - Embeddings    │
│  - Thumbnails   │            │  - Searchable    │
│  - Processing   │            │                  │
│    time         │            │                  │
└────────┬────────┘            └────────┬─────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
                    ▼
         ┌────────────────────┐
         │  API RESPONSE      │
         │                    │
         │  - Processing time │
         │  - Extraction      │
         │    method          │
         │  - Page count      │
         │  - Status          │
         │  - Thumbnail path  │
         └────────────────────┘
```

---

## Decision Tree

```
FILE UPLOADED
    │
    ├─ MIME Type Valid?
    │      ├─ Yes → Continue
    │      └─ No  → Reject (400 Error)
    │
    ├─ File Type?
    │      ├─ PDF
    │      │    ├─ Has Images?
    │      │    │    ├─ Yes + Size >10MB → Compress → OCR
    │      │    │    ├─ Yes + Size ≤10MB → OCR
    │      │    │    └─ No → OCR
    │      │    └─ Generate Thumbnail
    │      │
    │      ├─ DOCX
    │      │    ├─ Has Images (XML)?
    │      │    │    ├─ Yes → Convert to PDF (Gotenberg)
    │      │    │    │         ├─ Size >10MB → Compress
    │      │    │    │         └─ Size ≤10MB → Continue
    │      │    │    │         └─ OCR + Thumbnail + Save PDF
    │      │    │    └─ No → Text Extraction (PyMuPDF)
    │      │
    │      └─ DOC
    │           └─ Convert to PDF → Process as PDF
    │
    ├─ Store in PostgreSQL
    │    ├─ Full document content (JSON)
    │    ├─ Metadata (file size, extraction method, time)
    │    ├─ Thumbnail path
    │    └─ PDF path (if converted from DOCX)
    │
    └─ Store in pgvector
         ├─ Split into chunks (800 chars, 300 overlap)
         ├─ Generate embeddings (OpenAI)
         └─ Insert into collection
```

---

## Data Flow

```
┌─────────────┐
│   Client    │
│   Upload    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  FastAPI Endpoint                   │
│  /api/content-extractor-v2/         │
│  extract-files                      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  DocumentProcessor                  │
│  - validate_mime_type()             │
│  - check_pdf_has_images()           │
│  - check_docx_has_images()          │
│  - compress_pdf_with_ghostscript()  │
│  - convert_docx_to_pdf_gotenberg()  │
│  - process_pdf_with_ocr()           │
│  - generate_pdf_thumbnail()         │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  External Services                  │
│  ┌──────────────────────────────┐   │
│  │ Gotenberg                    │   │
│  │ DOCX → PDF conversion        │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ OpenRouter (Gemini)          │   │
│  │ OCR with mistral-ocr plugin  │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ OpenAI                       │   │
│  │ Embeddings generation        │   │
│  └──────────────────────────────┘   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Data Storage                       │
│  ┌──────────────────────────────┐   │
│  │ PostgreSQL                   │   │
│  │ - KnowledgeBase table        │   │
│  │ - Full documents             │   │
│  │ - Metadata                   │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ pgvector                     │   │
│  │ - Chunked documents          │   │
│  │ - Vector embeddings          │   │
│  │ - Semantic search            │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ File System                  │   │
│  │ - Thumbnails (PNG)           │   │
│  │ - Converted PDFs             │   │
│  └──────────────────────────────┘   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Response to Client                 │
│  - Processing metrics               │
│  - Extraction methods               │
│  - Success/failure status           │
│  - Storage confirmation             │
└─────────────────────────────────────┘
```

---

## Markdown Content Format

**OCR Output Example:**

```markdown
# Annual Report 2024

## Executive Summary

**Key Highlights:**
- Revenue increased by 25%
- Customer satisfaction: 4.8/5
- New product launches: 12

### Financial Performance

| Quarter | Revenue | Profit |
|---------|---------|--------|
| Q1      | $2.5M   | $450K  |
| Q2      | $3.1M   | $580K  |
| Q3      | $2.9M   | $520K  |
| Q4      | $3.8M   | $720K  |

![Sales Chart showing quarterly growth](Image on page 3)

*Caption: Quarterly revenue trend for 2024*

### Market Analysis

The market showed **strong growth** in the following segments:
1. Enterprise solutions
2. Cloud services
3. Mobile applications

> "Our strategy focuses on customer-centric innovation."
> — CEO Statement

---

**Conclusion:** The year demonstrated solid performance across all metrics.
```

---

## File Lifecycle

```
1. UPLOAD
   ├─ Temp file created
   ├─ MIME validation
   └─ Processing begins

2. PROCESSING
   ├─ Image detection
   ├─ Compression (if needed)
   ├─ Extraction (OCR or text)
   ├─ Thumbnail generation
   └─ PDF conversion (DOCX only)

3. STORAGE
   ├─ PostgreSQL: Full document + metadata
   ├─ pgvector: Chunked + embedded
   └─ File system: Thumbnails + PDFs

4. CLEANUP
   └─ Temp files deleted

5. RETRIEVAL
   ├─ View: GET /documents
   └─ Delete: DELETE /documents/{id}
        ├─ Remove from PostgreSQL
        ├─ Delete thumbnail
        └─ Delete PDF (if exists)
```

---

## Performance Optimization Points

```
┌────────────────────────────────────────┐
│  Optimization Strategy                 │
└────────────────────────────────────────┘

1. Async Operations
   - File uploads: asyncio.gather()
   - Subprocess calls: asyncio.create_subprocess_exec()
   - HTTP requests: run_in_executor()

2. Conditional Processing
   - Compression only if >10MB + images
   - DOCX conversion only if has images
   - Thumbnail only for visual documents

3. Batch Operations
   - Multiple files uploaded together
   - Single pgvector insertion for all chunks
   - Database commit after all processing

4. Caching
   - Reuse pgvector collection name
   - Avoid re-indexing existing embeddings

5. Resource Management
   - Temp files cleaned up in finally blocks
   - Database transactions with rollback
   - Executor threads for blocking operations
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────┐
│  Error Handling at Each Stage           │
└─────────────────────────────────────────┘

UPLOAD
├─ Invalid file type → 400 Error
├─ File size exceeded → 400 Error
└─ Corrupt file → 400 Error

MIME VALIDATION
├─ Invalid MIME → Reject file
└─ Continue to processing

IMAGE DETECTION
├─ PyMuPDF error → Log warning, assume no images
└─ Continue

COMPRESSION
├─ Ghostscript failed → Use original file
└─ Continue

OCR
├─ API error → Retry (built into OCR function)
├─ Parse error → Use fallback parsing
└─ Complete failure → Mark file as error

THUMBNAIL
├─ Generation failed → Continue (thumbnail optional)
└─ Continue

DATABASE
├─ Insert failed → Rollback transaction
├─ Commit failed → Rollback, return error
└─ Success → Return response

CLEANUP
└─ Always runs in finally block
```

---

## Summary

This visual guide shows the complete flow from file upload to storage. Key points:

- **3 main paths:** PDF, DOCX with images, DOCX without images
- **Intelligent routing:** Based on file type and content analysis
- **Multiple validations:** MIME, size, image detection
- **Dual storage:** PostgreSQL (full docs) + pgvector (semantic search)
- **Rich metadata:** Processing time, extraction method, thumbnails
- **Error resilience:** Fallbacks at every stage
