import os
import magic
import asyncio
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Any
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import fitz  # PyMuPDF
import requests
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Enhanced document processor with MIME type validation, image detection,
    compression, and thumbnail generation
    """

    def __init__(self, gotenberg_url: str = "http://localhost:3000"):
        self.gotenberg_url = gotenberg_url

    def validate_mime_type(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate MIME type of uploaded file

        Note: DOCX files are ZIP archives, so python-magic may detect them as
        application/zip. We validate by checking file extension as fallback.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, detected_mime_type)
        """
        try:
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(file_path)

            valid_mimes = {
                "application/pdf": "pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "application/msword": "doc",
                "application/zip": "docx",  # DOCX files are ZIP archives
            }

            # If detected as zip, verify it's actually a DOCX by checking extension
            if detected_mime == "application/zip":
                file_ext = Path(file_path).suffix.lower()
                if file_ext in [".docx", ".xlsx", ".pptx"]:
                    # It's an Office file (ZIP-based format)
                    logger.info(f"Detected as ZIP, but file extension is {file_ext} - accepting as Office document")
                    return True, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                else:
                    # It's a plain ZIP file, not an Office document
                    return False, detected_mime

            if detected_mime in valid_mimes:
                return True, detected_mime
            else:
                return False, detected_mime

        except Exception as e:
            logger.error(f"Error validating MIME type for {file_path}: {str(e)}")
            return False, "unknown"

    def check_pdf_has_images(self, file_path: str) -> bool:
        """
        Check if PDF contains images using PyMuPDF
        Returns immediately upon finding first image for performance

        Args:
            file_path: Path to PDF file

        Returns:
            bool: True if PDF contains at least one image
        """
        try:
            doc = fitz.open(file_path)
            has_images = False

            # Early exit - stop as soon as first image is found
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                if len(image_list) > 0:
                    has_images = True
                    logger.info(f"PDF has images (detected on page {page_num + 1})")
                    break  # Early exit for performance

            doc.close()

            if not has_images:
                logger.info("PDF has no images")

            return has_images

        except Exception as e:
            logger.error(f"Error checking PDF images for {file_path}: {str(e)}")
            return False

    async def compress_pdf_with_ghostscript(
        self, input_path: str, output_path: str
    ) -> bool:
        """
        Compress PDF using Ghostscript (async version)

        Args:
            input_path: Path to input PDF
            output_path: Path to save compressed PDF

        Returns:
            bool: True if successful
        """
        try:
            gs_command = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/ebook",  # Better quality than /screen
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dDetectDuplicateImages=true",
                "-dCompressFonts=true",
                "-dSubsetFonts=true",
                "-dColorImageDownsampleType=/Bicubic",
                "-dColorImageResolution=150",
                "-dGrayImageDownsampleType=/Bicubic",
                "-dGrayImageResolution=150",
                "-dMonoImageDownsampleType=/Bicubic",
                "-dMonoImageResolution=150",
                f"-sOutputFile={output_path}",
                input_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *gs_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                original_size = os.path.getsize(input_path) / (1024 * 1024)
                compressed_size = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(
                    f"PDF compressed: {original_size:.1f}MB -> {compressed_size:.1f}MB"
                )
                return True
            else:
                logger.error(f"Ghostscript compression failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error compressing PDF: {str(e)}")
            return False

    def check_docx_has_images(self, file_path: str) -> bool:
        """
        Check if DOCX contains images by parsing XML content
        Returns immediately upon finding first image for performance

        Args:
            file_path: Path to DOCX file

        Returns:
            bool: True if DOCX contains at least one image
        """
        try:
            with ZipFile(file_path, "r") as docx:
                # Quick check: media folder exists and has files
                media_files = [
                    name
                    for name in docx.namelist()
                    if name.startswith("word/media/")
                ]

                if len(media_files) > 0:
                    logger.info(f"DOCX has images (found in word/media/)")
                    return True

                # Secondary check: document.xml for image references
                if "word/document.xml" in docx.namelist():
                    doc_xml = docx.read("word/document.xml")
                    root = ET.fromstring(doc_xml)

                    # Look for image tags
                    namespaces = {
                        "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
                    }

                    # Find first pic:pic element
                    pic = root.find(".//pic:pic", namespaces)
                    if pic is not None:
                        logger.info(f"DOCX has images (found in XML)")
                        return True

            logger.info("DOCX has no images")
            return False

        except Exception as e:
            logger.error(f"Error checking DOCX images for {file_path}: {str(e)}")
            return False

    async def convert_docx_to_pdf_gotenberg(
        self, docx_path: str, output_pdf_path: str
    ) -> bool:
        """
        Convert DOCX to PDF using Gotenberg API

        Args:
            docx_path: Path to DOCX file
            output_pdf_path: Path to save converted PDF

        Returns:
            bool: True if successful
        """
        try:
            url = f"{self.gotenberg_url}/forms/libreoffice/convert"

            with open(docx_path, "rb") as f:
                files = {"files": (os.path.basename(docx_path), f)}
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: requests.post(url, files=files, timeout=60)
                )

            if response.status_code == 200:
                with open(output_pdf_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"DOCX converted to PDF: {output_pdf_path}")
                return True
            else:
                logger.error(
                    f"Gotenberg conversion failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error converting DOCX to PDF: {str(e)}")
            return False

    async def generate_pdf_thumbnail(
        self, pdf_path: str, thumbnail_path: str, dpi: int = 150
    ) -> bool:
        """
        Generate thumbnail of first page of PDF

        Args:
            pdf_path: Path to PDF file
            thumbnail_path: Path to save thumbnail
            dpi: DPI for thumbnail quality

        Returns:
            bool: True if successful
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                logger.error(f"PDF has no pages: {pdf_path}")
                return False

            # Get first page
            page = doc[0]

            # Calculate zoom for desired DPI
            zoom = dpi / 72  # 72 is the default DPI
            mat = fitz.Matrix(zoom, zoom)

            # Render page to image
            pix = page.get_pixmap(matrix=mat)

            # Save as PNG
            pix.save(thumbnail_path)
            doc.close()

            logger.info(f"Thumbnail generated: {thumbnail_path}")
            return True

        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return False

    async def process_pdf_with_ocr(
        self,
        pdf_path: str,
        openrouter_api_key: str,
        original_filename: str = None,
    ) -> List[Document]:
        """
        Process PDF with OCR using OpenRouter (Gemini 2.5 Flash)
        Enhanced to preserve tables and image formatting

        Args:
            pdf_path: Path to PDF file
            openrouter_api_key: OpenRouter API key
            original_filename: Original filename

        Returns:
            List of Document objects
        """
        try:
            import base64

            # Read and encode PDF
            with open(pdf_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
            }

            # Enhanced prompt to preserve tables and images
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are an expert OCR system. Extract ALL text from this PDF with the following requirements:

## CRITICAL: MARKDOWN OUTPUT FORMAT
- Your entire response must be valid JSON starting with `[` and ending with `]`
- NO explanatory text, NO markdown code blocks, NO extra content
- Each page should be a separate JSON object

## FORMATTING RULES:
1. **Tables**: Convert ALL tables to markdown format:
   ```
   | Header 1 | Header 2 | Header 3 |
   |----------|----------|----------|
   | Cell 1   | Cell 2   | Cell 3   |
   ```

2. **Images**: When you encounter an image, include:
   ```
   ![Image Description](Image on page X)

   Caption: [Include any visible caption text]
   ```

3. **Text Formatting**: Preserve:
   - **Bold text** using **double asterisks**
   - *Italic text* using *single asterisks*
   - Headings using # symbols (# H1, ## H2, etc.)
   - Lists using - or 1. 2. 3.
   - Code blocks using triple backticks if present

4. **Structure**:
   - Maintain paragraph breaks
   - Preserve section hierarchy
   - Keep bullet points and numbering
   - Maintain text flow and reading order

## EXACT JSON FORMAT:
[
  {
    "page_content": "# Page 1 Title\\n\\n**Bold text** and regular text.\\n\\n| Col1 | Col2 |\\n|------|------|\\n| A    | B    |\\n\\n![Chart](Image on page 1)\\n\\nMore content..."
  },
  {
    "page_content": "Page 2 content in markdown format..."
  }
]

## ESCAPING:
- Escape quotes: \\"
- Escape newlines: \\n
- Escape backslashes: \\\\

Extract the content now. Return ONLY the JSON array:""",
                        },
                        {
                            "type": "file",
                            "file": {
                                "filename": os.path.basename(pdf_path),
                                "file_data": f"data:application/pdf;base64,{pdf_base64}",
                            },
                        },
                    ],
                }
            ]

            # Use Gemini 2.5 Flash via OpenRouter with OCR plugin
            plugins = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]

            payload = {
                "model": "google/gemini-2.0-flash-001:free",
                "messages": messages,
                "plugins": plugins,
            }

            # Make request
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.post(url, headers=headers, json=payload)
            )

            if response.status_code != 200:
                raise ValueError(f"OCR request failed: {response.status_code}")

            response_data = response.json()
            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            # Parse response
            import json

            content_list = self._parse_ocr_response(content)

            # Convert to Document objects
            documents = []
            for i, page_data in enumerate(content_list):
                page_content = page_data.get("page_content", "")
                documents.append(
                    Document(
                        page_content=page_content,
                        metadata={
                            "page": i + 1,
                            "source": original_filename or pdf_path,
                            "extraction_method": "ocr",
                        },
                    )
                )

            logger.info(f"OCR completed: {len(documents)} pages extracted")
            return documents

        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            raise

    def _parse_ocr_response(self, content: str) -> List[dict]:
        """Parse OCR response with fallback strategies"""
        import json
        import re

        # Strategy 1: Direct JSON parsing
        try:
            content_list = json.loads(content)
            if isinstance(content_list, list):
                return content_list
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON from response
        try:
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            start_idx = cleaned.find("[")
            end_idx = cleaned.rfind("]")

            if start_idx != -1 and end_idx != -1:
                json_part = cleaned[start_idx : end_idx + 1]
                content_list = json.loads(json_part)
                if isinstance(content_list, list):
                    return content_list
        except:
            pass

        # Strategy 3: Fallback - treat as single page
        return [{"page_content": content.strip()}]

    def get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB"""
        return os.path.getsize(file_path) / (1024 * 1024)