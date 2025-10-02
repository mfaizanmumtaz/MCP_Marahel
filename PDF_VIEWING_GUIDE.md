# PDF Viewing & Download - Phase 1 Implementation

## Overview

PDF files (converted from DOCX/DOC) can now be viewed and downloaded through API endpoints.

---

## API Endpoints

### 1. **Get All Documents (with URLs)**

```bash
GET /api/content-extractor-v2/documents?tenant_id={tenant_id}
```

**Response:**
```json
{
  "tenant_id": "tenant123",
  "total_documents": 3,
  "documents": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "filename": "report.docx",
      "file_type": "docx",
      "file_size_mb": "8.92",
      "extraction_method": "docx_conversion_ocr",
      "page_count": "15",
      "created_at": "2025-01-02T10:30:00",
      "thumbnail_url": "/api/content-extractor-v2/documents/123e4567.../thumbnail?tenant_id=tenant123",
      "pdf_url": "/api/content-extractor-v2/documents/123e4567.../pdf?tenant_id=tenant123"
    }
  ]
}
```

---

### 2. **View/Download PDF**

```bash
GET /api/content-extractor-v2/documents/{document_id}/pdf?tenant_id={tenant_id}
```

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `inline` (opens in browser)
- File is served directly

**Security:**
- ✅ Verifies tenant_id matches document owner
- ✅ Checks file exists before serving
- ✅ Returns 404 if PDF not available

---

### 3. **Get Thumbnail**

```bash
GET /api/content-extractor-v2/documents/{document_id}/thumbnail?tenant_id={tenant_id}
```

**Response:**
- Content-Type: `image/png`
- PNG image of first page (150 DPI)

---

## Usage Examples

### **JavaScript/React:**

```javascript
// Fetch document list
const response = await fetch(
  '/api/content-extractor-v2/documents?tenant_id=tenant123'
);
const data = await response.json();

// Display thumbnails
{data.documents.map(doc => (
  <div key={doc.id}>
    <h3>{doc.filename}</h3>

    {/* Thumbnail preview */}
    {doc.thumbnail_url && (
      <img
        src={doc.thumbnail_url}
        alt={doc.filename}
        style={{width: '200px'}}
      />
    )}

    {/* View PDF in new tab */}
    {doc.pdf_url && (
      <a href={doc.pdf_url} target="_blank">
        View PDF
      </a>
    )}

    {/* Download PDF */}
    {doc.pdf_url && (
      <a href={doc.pdf_url} download>
        Download PDF
      </a>
    )}
  </div>
))}
```

---

### **HTML:**

```html
<!-- View PDF in iframe -->
<iframe
  src="/api/content-extractor-v2/documents/123e4567.../pdf?tenant_id=tenant123"
  width="100%"
  height="600px">
</iframe>

<!-- Thumbnail preview -->
<img
  src="/api/content-extractor-v2/documents/123e4567.../thumbnail?tenant_id=tenant123"
  alt="Document preview"
/>

<!-- Download link -->
<a href="/api/content-extractor-v2/documents/123e4567.../pdf?tenant_id=tenant123" download>
  Download PDF
</a>
```

---

### **cURL:**

```bash
# View PDF
curl "http://localhost:9696/api/content-extractor-v2/documents/{doc_id}/pdf?tenant_id=tenant123" \
  --output document.pdf

# Get thumbnail
curl "http://localhost:9696/api/content-extractor-v2/documents/{doc_id}/thumbnail?tenant_id=tenant123" \
  --output thumbnail.png
```

---

## File Availability

### **When PDFs are Available:**

| Original File Type | PDF Available? | Reason |
|-------------------|----------------|--------|
| PDF (uploaded) | ❌ No | Original is already PDF (not saved again) |
| DOCX with images | ✅ Yes | Converted to PDF for OCR |
| DOCX without images | ❌ No | Text extraction used (no conversion) |
| DOC | ✅ Yes | Always converted to PDF |

### **When Thumbnails are Available:**

| File Type | Thumbnail Available? |
|-----------|---------------------|
| PDF | ✅ Yes |
| DOCX with images | ✅ Yes (from converted PDF) |
| DOCX without images | ❌ No |
| DOC | ✅ Yes (from converted PDF) |

---

## Storage Structure

```
storage/
└── {tenant_id}/
    ├── thumbnails/
    │   ├── report_1704123456.png      # Thumbnail (150 DPI PNG)
    │   └── document_1704123789.png
    └── pdfs/
        └── document_1704123789.pdf    # Converted DOCX→PDF
```

- Files are isolated per tenant
- Timestamped filenames prevent collisions
- Automatically deleted when document is removed

---

## Error Handling

### **404 Errors:**

```json
// PDF not available
{
  "detail": "PDF not available for this document (original file type: pdf)"
}

// File deleted
{
  "detail": "PDF file not found on server"
}

// Document doesn't exist
{
  "detail": "Document '123...' not found for tenant 'tenant123'"
}
```

### **Security:**

- ✅ Tenant verification on every request
- ✅ Document ownership check
- ✅ File existence validation
- ✅ No directory traversal vulnerabilities

---

## Performance Considerations

### **Current Implementation:**

- Files served directly from disk
- No caching (browsers handle it)
- Fast for local/single-server deployments

### **Optimization Tips:**

1. **Add CDN caching:**
   ```python
   headers={
       "Cache-Control": "public, max-age=3600"
   }
   ```

2. **Enable gzip compression** in nginx/uvicorn

3. **For production:** Consider Phase 2 (S3 migration)

---

## Complete Example

### **Upload → View → Download Flow:**

```bash
# 1. Upload DOCX file
curl -X POST "http://localhost:9696/api/content-extractor-v2/extract-files" \
  -F "files=@report.docx" \
  -F "tenant_id=tenant123" \
  -F "summary_access=true" \
  -F "translation_access=true" \
  -F "rag_access=true" \
  -F "cag_access=true"

# Response includes document ID
# {
#   "files": [{"filename": "report.docx", "status": "success"}],
#   ...
# }

# 2. Get document list with URLs
curl "http://localhost:9696/api/content-extractor-v2/documents?tenant_id=tenant123"

# Response:
# {
#   "documents": [
#     {
#       "id": "abc-123",
#       "pdf_url": "/api/content-extractor-v2/documents/abc-123/pdf?tenant_id=tenant123",
#       "thumbnail_url": "/api/content-extractor-v2/documents/abc-123/thumbnail?tenant_id=tenant123"
#     }
#   ]
# }

# 3. View PDF
curl "http://localhost:9696/api/content-extractor-v2/documents/abc-123/pdf?tenant_id=tenant123" \
  --output report.pdf

# 4. Get thumbnail
curl "http://localhost:9696/api/content-extractor-v2/documents/abc-123/thumbnail?tenant_id=tenant123" \
  --output thumbnail.png
```

---

## Frontend Integration

### **React Component Example:**

```jsx
import React, { useState, useEffect } from 'react';

function DocumentViewer({ tenantId }) {
  const [documents, setDocuments] = useState([]);

  useEffect(() => {
    fetch(`/api/content-extractor-v2/documents?tenant_id=${tenantId}`)
      .then(res => res.json())
      .then(data => setDocuments(data.documents));
  }, [tenantId]);

  return (
    <div className="document-grid">
      {documents.map(doc => (
        <div key={doc.id} className="document-card">
          <h3>{doc.filename}</h3>

          {/* Thumbnail */}
          {doc.thumbnail_url && (
            <img
              src={doc.thumbnail_url}
              alt={doc.filename}
              className="thumbnail"
            />
          )}

          {/* PDF Actions */}
          {doc.pdf_url && (
            <div className="actions">
              <button onClick={() => window.open(doc.pdf_url, '_blank')}>
                View PDF
              </button>
              <a href={doc.pdf_url} download>
                <button>Download</button>
              </a>
            </div>
          )}

          {/* Metadata */}
          <div className="metadata">
            <span>Type: {doc.file_type}</span>
            <span>Size: {doc.file_size_mb} MB</span>
            <span>Pages: {doc.page_count}</span>
            <span>Method: {doc.extraction_method}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## Next Steps (Phase 2)

When you need to scale:

1. **Migrate to S3/Cloud Storage**
2. **Generate pre-signed URLs** (time-limited access)
3. **Add CDN** for global distribution
4. **Implement background jobs** for large files

---

## Summary

✅ **Phase 1 Complete:**
- PDF viewing via API endpoints
- Thumbnail preview support
- Download functionality
- Tenant-level security
- Simple file system storage

**Ready to use immediately!** No additional setup required beyond existing infrastructure.
