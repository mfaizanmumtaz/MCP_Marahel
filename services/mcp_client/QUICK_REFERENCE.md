# Content Extractor V2 - Quick Reference

## Setup (5 minutes)

```bash
# 1. Install dependencies
pip install python-magic python-magic-bin PyMuPDF requests

# 2. Start Gotenberg
docker run -d -p 3000:3000 gotenberg/gotenberg:8

# 3. Set environment variables
export GOTENBERG_URL=http://localhost:3000
export OPENROUTER_API_KEY=your_key
export OPENAI_API_KEY=your_key

# 4. Run migration
cd services/mcp_client/src
python -m ingestion_api.db.models

# 5. Start server
make dev
```

---

## API Quick Start

### Upload Files
```bash
curl -X POST "http://localhost:9696/api/content-extractor-v2/extract-files" \
  -F "files=@document.pdf" \
  -F "files=@report.docx" \
  -F "tenant_id=my_tenant" \
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"
```

### View Documents
```bash
curl "http://localhost:9696/api/content-extractor-v2/documents?tenant_id=my_tenant"
```

### Delete Document
```bash
curl -X DELETE \
  "http://localhost:9696/api/content-extractor-v2/documents/{doc_id}?tenant_id=my_tenant"
```

---

## Processing Logic

### PDF
```
PDF → MIME Check → Image Detection → Compress (if >10MB + images) → OCR → Thumbnail → DB
```

### DOCX with Images
```
DOCX → MIME Check → XML Parse → Convert to PDF → Compress (if >10MB) → OCR → Thumbnail → DB
```

### DOCX without Images
```
DOCX → MIME Check → XML Parse → Text Extract → DB
```

---

## Response Format

```json
{
  "processing_time_seconds": "45.32",
  "files": [
    {
      "filename": "report.pdf",
      "extraction_method": "ocr",
      "page_count": 15,
      "processing_time_seconds": "23.45"
    }
  ],
  "summary": {
    "extraction_methods_used": {
      "ocr": 2,
      "text_extraction": 1
    }
  }
}
```

---

## Extraction Methods

| Method | Description |
|--------|-------------|
| `ocr` | OCR with markdown formatting |
| `text_extraction` | Direct text extraction |
| `docx_conversion_ocr` | DOCX → PDF → OCR |

---

## Storage Structure

```
storage/
└── {tenant_id}/
    ├── thumbnails/
    │   └── file_{timestamp}.png
    └── pdfs/
        └── file_{timestamp}.pdf
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Invalid MIME type | File corrupted or wrong extension |
| Gotenberg failed | `docker start gotenberg` |
| No thumbnails | `pip install PyMuPDF` |
| OCR errors | Check OPENROUTER_API_KEY |

---

## Key Features

✅ MIME validation
✅ Auto compression
✅ OCR with tables
✅ Thumbnails
✅ Individual deletion
✅ Processing metrics
✅ Markdown format

---

## Important Changes from V1

- ❌ **user_id removed** (tenant-level only)
- ✅ **Individual file tracking** (can delete single files)
- ✅ **Processing time** in response
- ✅ **Extraction method** per file
- ✅ **Thumbnails** auto-generated

---

## Environment Variables

```bash
GOTENBERG_URL=http://localhost:3000
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-...
```

---

## Database Schema

```python
KnowledgeBase:
  - id (UUID)
  - tenant_id (FK)
  - filename
  - file_type (pdf/docx/doc)
  - extraction_method
  - processing_time_seconds
  - thumbnail_path
  - pdf_path
  - page_count
```

---

## API Documentation

Full docs: `http://localhost:9696/docs`

Endpoints:
- `POST /api/content-extractor-v2/extract-files`
- `GET /api/content-extractor-v2/documents`
- `DELETE /api/content-extractor-v2/documents/{id}`
- `GET /api/content-extractor-v2/formats`
