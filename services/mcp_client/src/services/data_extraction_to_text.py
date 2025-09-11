import os
import asyncio
import aiofiles
import tempfile
import shutil
from typing import List, Union, Any
from pathlib import Path
import logging

# LangChain imports
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_community.document_loaders import UnstructuredExcelLoader
from langchain_community.document_loaders import Docx2txtLoader
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())
# OpenAI import
from openai import AsyncOpenAI

# PDF and DOCX compression imports
import fitz  # PyMuPDF
from zipfile import ZipFile, ZIP_DEFLATED

# Audio compression imports
import subprocess
import platform
import math
import shutil

# PDF scan detection imports
import PyPDF2
import pdfplumber
from PIL import Image
import io
import requests
import json
import base64
import re

# Set up logging
log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)
handler = logging.FileHandler(os.path.join(log_dir, "content_extractor_api_utils.log"))
handler.setFormatter(formatter)
logger.addHandler(handler)


class UniversalFileLoader:
    """
    A comprehensive async file loader class that handles multiple file types:
    PDF, PPTX, DOCX, DOC, MP3, WAV, Excel, CSV
    """
    
    def __init__(self, openai_api_key: str = None, openrouter_api_key: str = None):
        """
        Initialize the UniversalFileLoader
        
        Args:
            openai_api_key: OpenAI API key for audio transcription (optional if set in environment)
            openrouter_api_key: OpenRouter API key for OCR scanning (optional if set in environment)
        """
        self.client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else AsyncOpenAI()
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        
        # Supported file extensions
        self.supported_extensions = {
            '.pdf': self.load_pdf,
            '.pptx': self.load_pptx,
            '.docx': self.load_docx,
            '.doc': self.load_doc,
            '.mp3': self.load_mp3,
            '.wav': self.load_wav,
            '.xlsx': self.load_excel,
            '.xls': self.load_excel,
            '.csv': self.load_csv
        }
    
    def get_file_extension(self, file_path: str) -> str:
        """Get file extension from path"""
        return Path(file_path).suffix.lower()
    
    def validate_file_exists(self, file_path: str) -> bool:
        """Validate if file exists"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        return True

    def get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB"""
        return os.path.getsize(file_path) / (1024 * 1024)

    def _update_document_metadata(self, documents: List[Any], original_filename: str = None) -> List[Any]:
        """
        Update document metadata to use original filename instead of temp path
        
        Args:
            documents: List of document objects
            original_filename: Original filename to use in metadata
            
        Returns:
            Updated documents with corrected metadata
        """
        if not original_filename or not documents:
            return documents
            
        for doc in documents:
            if hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
                # Update the source to use original filename
                doc.metadata['source'] = original_filename
        
        return documents

    async def compress_pdf(self, input_path: str, output_path: str) -> bool:
        """
        Compress PDF file using Ghostscript (gs)

        Args:
            input_path: Path to input PDF file
            output_path: Path to save compressed PDF

        Returns:
            bool: True if compression successful, False otherwise
        """
        try:
            # Construct the Ghostscript command
            gs_command = [
    'gs',
    '-sDEVICE=pdfwrite',
    '-dCompatibilityLevel=1.4',
    '-dPDFSETTINGS=/screen',  # Aggressive compression
    '-dNOPAUSE',
    '-dQUIET',
    '-dBATCH',
    '-dDetectDuplicateImages=true',
    '-dCompressFonts=true',
    '-dSubsetFonts=true',
    '-dColorImageDownsampleType=/Bicubic',
    '-dColorImageResolution=72',
    '-dGrayImageDownsampleType=/Bicubic',
    '-dGrayImageResolution=72',
    '-dMonoImageDownsampleType=/Subsample',
    '-dMonoImageResolution=72',
    '-dEncodeColorImages=true',
    '-dEncodeGrayImages=true',
    '-dEncodeMonoImages=true',
    '-dColorImageFilter=/DCTEncode',
    '-dGrayImageFilter=/DCTEncode',
    '-dMonoImageFilter=/CCITTFaxEncode',
    f'-sOutputFile={output_path}',
    input_path
]


            # Run the Ghostscript command
            result = subprocess.run(gs_command, capture_output=True, text=True)

            if result.returncode == 0:
                compressed_size_mb = self.get_file_size_mb(output_path)
                logger.info(f"PDF successfully compressed to {compressed_size_mb:.1f}MB using Ghostscript")
                return True
            else:
                logger.error(f"Ghostscript compression failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error compressing PDF {input_path} with Ghostscript: {str(e)}")
            return False

    async def compress_docx(self, input_path: str, output_path: str) -> bool:
        """
        Compress DOCX file by repackaging with higher compression

        Args:
            input_path: Path to input DOCX file
            output_path: Path to save compressed DOCX

        Returns:
            bool: True if compression successful, False otherwise
        """
        try:
            # DOCX files are ZIP archives, so we can recompress them
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_extract_dir = os.path.join(temp_dir, "docx_content")

                # Extract the DOCX content
                with ZipFile(input_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)

                # Repackage with maximum compression
                with ZipFile(output_path, 'w', ZIP_DEFLATED, compresslevel=9) as zip_out:
                    for root, dirs, files in os.walk(temp_extract_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, temp_extract_dir)
                            zip_out.write(file_path, arc_name)

                compressed_size_mb = self.get_file_size_mb(output_path)
                logger.info(f"DOCX compressed to {compressed_size_mb:.1f}MB")

                return True

        except Exception as e:
            logger.error(f"Error compressing DOCX {input_path}: {str(e)}")
            return False

    async def compress_wav(self, input_path: str, output_path: str, target_size_mb: float = 100) -> bool:
        """
        Compress WAV file to reduce size using ffmpeg
        
        Args:
            input_path: Path to input WAV file
            output_path: Path to save compressed WAV
            target_size_mb: Target size in MB (default: 100MB)
            
        Returns:
            bool: True if compression successful and under target size, False otherwise
        """
        try:
            # Check if ffmpeg is available
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("ffmpeg not found. Cannot compress WAV files.")
                return False
            
            original_size_mb = self.get_file_size_mb(input_path)
            logger.info(f"Original WAV file size: {original_size_mb:.1f}MB")
            
            # Try different compression strategies
            compression_strategies = [
                # Strategy 1: Reduce bitrate
                ['-i', input_path, '-acodec', 'pcm_s16le', '-ar', '22050', output_path],
                # Strategy 2: More aggressive bitrate reduction
                ['-i', input_path, '-acodec', 'pcm_s16le', '-ar', '16000', output_path],
                # Strategy 3: Convert to mono and reduce bitrate
                ['-i', input_path, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path],
                # Strategy 4: Most aggressive - very low sample rate, mono
                ['-i', input_path, '-acodec', 'pcm_s16le', '-ar', '8000', '-ac', '1', output_path]
            ]
            
            for i, strategy in enumerate(compression_strategies):
                try:
                    # Remove output file if it exists
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                    
                    # Run ffmpeg compression
                    result = subprocess.run(
                        ['ffmpeg'] + strategy,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode == 0 and os.path.exists(output_path):
                        compressed_size_mb = self.get_file_size_mb(output_path)
                        logger.info(f"WAV compression strategy {i+1}: {compressed_size_mb:.1f}MB")
                        
                        if compressed_size_mb <= target_size_mb:
                            logger.info(f"WAV successfully compressed from {original_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")
                            return True
                    else:
                        logger.warning(f"WAV compression strategy {i+1} failed: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    logger.error(f"WAV compression strategy {i+1} timed out")
                    continue
                except Exception as strategy_e:
                    logger.warning(f"WAV compression strategy {i+1} error: {str(strategy_e)}")
                    continue
            
            # All strategies failed
            final_size_mb = self.get_file_size_mb(output_path) if os.path.exists(output_path) else original_size_mb
            logger.error(f"WAV compression failed. Final size: {final_size_mb:.1f}MB")
            return False
            
        except Exception as e:
            logger.error(f"Error compressing WAV {input_path}: {str(e)}")
            return False

    def get_audio_duration(self, file_path: str) -> float:
        """Get duration of audio in seconds using ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                logger.error(f"Error getting audio duration: {result.stderr}")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting audio duration for {file_path}: {str(e)}")
            return 0.0

    async def compress_audio_to_target_size(self, input_path: str, output_path: str, target_size_mb: float = 25) -> bool:
        """
        Compress audio file to target size using ffmpeg with dynamic bitrate calculation
        Always compresses for optimization, even if file is already under target size
        
        Args:
            input_path: Path to input audio file
            output_path: Path to save compressed audio
            target_size_mb: Target size in MB (default: 25MB)
            
        Returns:
            bool: True if compression successful and under target size, False otherwise
        """
        try:
            # Check if ffmpeg is available
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("ffmpeg not found. Cannot compress audio files.")
                return False

            target_size_bytes = target_size_mb * 1024 * 1024
            original_size = os.path.getsize(input_path)
            logger.info(f"Original size: {original_size/1024/1024:.2f} MB")

            # Get audio duration for bitrate calculation
            duration = self.get_audio_duration(input_path)
            if duration <= 0:
                logger.error("Could not determine audio duration")
                return False

            # Calculate target bitrate based on target size
            target_bitrate_kbps = int((target_size_bytes * 8) / duration / 1000)
            
            # Define compression strategies with different bitrates
            # Start with calculated bitrate, then try progressively lower bitrates if needed
            compression_strategies = [
                target_bitrate_kbps,
                max(32, target_bitrate_kbps * 0.8),  # 80% of target
                max(32, target_bitrate_kbps * 0.6),  # 60% of target
                max(32, target_bitrate_kbps * 0.4),  # 40% of target
                32  # Minimum acceptable bitrate for speech
            ]
            
            # Remove duplicates and ensure minimum bitrate
            compression_strategies = list(dict.fromkeys([max(32, int(br)) for br in compression_strategies]))
            
            logger.info(f"Audio duration: {duration:.1f}s, trying bitrates: {compression_strategies}")

            for i, bitrate_kbps in enumerate(compression_strategies):
                try:
                    # Remove output file if it exists
                    if os.path.exists(output_path):
                        os.unlink(output_path)

                    logger.info(f"Compression attempt {i+1}/{len(compression_strategies)} at {bitrate_kbps} kbps")

                    # Compress with current bitrate
                    result = subprocess.run([
                        "ffmpeg", "-y",
                        "-i", input_path,
                        "-b:a", f"{bitrate_kbps}k",
                        "-ar", "22050",  # Reduce sample rate for better compression
                        output_path
                    ], capture_output=True, text=True, timeout=300)

                    if result.returncode == 0 and os.path.exists(output_path):
                        final_size = os.path.getsize(output_path)
                        final_size_mb = final_size / 1024 / 1024
                        logger.info(f"Compressed size: {final_size_mb:.2f} MB")
                        
                        # If we achieved target size, return success
                        if final_size <= target_size_bytes:
                            logger.info(f"Successfully compressed from {original_size/1024/1024:.2f}MB to {final_size_mb:.2f}MB")
                            return True
                        elif i == len(compression_strategies) - 1:
                            # This was our last attempt and still too large
                            logger.warning(f"Final compression attempt resulted in {final_size_mb:.2f}MB (still > {target_size_mb}MB)")
                            return False
                        else:
                            # Try next lower bitrate
                            logger.info(f"Size {final_size_mb:.2f}MB still > {target_size_mb}MB, trying lower bitrate...")
                            continue
                    else:
                        logger.warning(f"Compression attempt {i+1} failed: {result.stderr}")
                        if i == len(compression_strategies) - 1:
                            # This was our last attempt
                            return False
                        continue
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"Compression attempt {i+1} timed out")
                    if i == len(compression_strategies) - 1:
                        return False
                    continue
                    
            # If we get here, all strategies failed
            logger.error("All compression strategies failed")
            return False
                
        except Exception as e:
            logger.error(f"Error compressing audio {input_path}: {str(e)}")
            return False

    async def convert_wav_to_mp3(self, input_path: str, output_path: str) -> bool:
        """
        Convert WAV file to MP3 format using ffmpeg
        
        Args:
            input_path: Path to input WAV file
            output_path: Path to save MP3 file
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        try:
            # Check if ffmpeg is available
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("ffmpeg not found. Cannot convert WAV to MP3.")
                return False
            
            original_size_mb = self.get_file_size_mb(input_path)
            logger.info(f"Converting WAV file ({original_size_mb:.1f}MB) to MP3...")
            
            # Remove output file if it exists
            if os.path.exists(output_path):
                os.unlink(output_path)
            
            # Convert WAV to MP3 with good quality settings
            # -codec:a libmp3lame: Use LAME MP3 encoder
            # -b:a 128k: Set audio bitrate to 128 kbps (good quality/size balance)
            # -ar 44100: Set sample rate to 44.1kHz (standard)
            result = subprocess.run([
                'ffmpeg',
                '-i', input_path,
                '-codec:a', 'libmp3lame',
                '-b:a', '128k',
                '-ar', '44100',
                output_path
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0 and os.path.exists(output_path):
                mp3_size_mb = self.get_file_size_mb(output_path)
                logger.info(f"WAV to MP3 conversion successful: {original_size_mb:.1f}MB -> {mp3_size_mb:.1f}MB")
                return True
            else:
                logger.error(f"WAV to MP3 conversion failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("WAV to MP3 conversion timed out")
            return False
        except Exception as e:
            logger.error(f"Error converting WAV to MP3 {input_path}: {str(e)}")
            return False
    
    # PyMuPDF supported formats (PDF, DOCX, DOC)
    async def load_pdf(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Load PDF file with intelligent scan detection and appropriate extraction method
        - First checks if PDF is scanned or extractable
        - Uses OpenRouter OCR for scanned PDFs
        - Uses standard extraction for extractable PDFs
        - Automatically compresses large PDFs if needed

        Args:
            file_path: Path to PDF file

        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)
            
            # Step 1: Analyze PDF to determine if it's scanned or extractable
            logger.info(f"Analyzing PDF to determine extraction method: {file_path}")
            analysis_result = analyze_pdf(file_path)
            
            classification = analysis_result.get('final_classification', 'UNCERTAIN')
            logger.info(f"PDF analysis result: {classification} - {analysis_result.get('recommendation', '')}")
            
            # Step 2: Route to appropriate extraction method based on classification
            if classification == "SCANNED":
                logger.info(f"PDF detected as SCANNED, using OpenRouter OCR for extraction")
                return await self._openrouter_ocr_scan(file_path, original_filename)
            
            elif classification == "EXTRACTABLE":
                logger.info(f"PDF detected as EXTRACTABLE, using standard text extraction")
                return await self._load_extractable_pdf(file_path, original_filename)
            
            else:  # MIXED or UNCERTAIN
                logger.info(f"PDF classification uncertain ({classification}), trying standard extraction first")
                try:
                    # Try standard extraction first
                    data = await self._load_extractable_pdf(file_path, original_filename)
                    
                    # Check if extraction was successful (has meaningful content)
                    total_text_length = sum(len(doc.page_content.strip()) for doc in data)
                    if total_text_length > 100:  # If we got reasonable amount of text
                        logger.info(f"Standard extraction successful for mixed PDF: {total_text_length} characters extracted")
                        return data
                    else:
                        logger.info(f"Standard extraction yielded minimal text ({total_text_length} chars), falling back to OCR")
                        return await self._openrouter_ocr_scan(file_path, original_filename)
                        
                except Exception as std_error:
                    logger.warning(f"Standard extraction failed for mixed PDF: {str(std_error)}, falling back to OCR")
                    return await self._openrouter_ocr_scan(file_path, original_filename)

        except Exception as e:
            logger.error(f"Error loading PDF {file_path}: {str(e)}")
            raise

    async def _load_extractable_pdf(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Load extractable PDF using standard methods with compression if needed
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of loaded document objects
        """
        try:
            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)

            # Always attempt compression for optimization
            logger.info(f"PDF file {file_path} is {file_size_mb:.1f}MB, attempting compression...")

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                compressed_path = temp_file.name

            try:
                # Attempt compression without size restriction
                compression_success = await self.compress_pdf(file_path, compressed_path)

                if compression_success and os.path.exists(compressed_path):
                    compressed_size_mb = self.get_file_size_mb(compressed_path)
                    logger.info(f"PDF successfully compressed from {file_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")

                    # Load the compressed file
                    loader = PyPDFLoader(compressed_path)
                    data = await loader.aload()
                    logger.info(f"Successfully loaded compressed PDF: {file_path} ({len(data)} pages)")
                    return self._update_document_metadata(data, original_filename or file_path)
                else:
                    # Compression failed, load original file
                    logger.info(f"PDF compression failed, loading original file: {file_path}")
                    loader = PyMuPDFLoader(file_path)
                    data = await loader.aload()
                    logger.info(f"Successfully loaded original PDF: {file_path} ({len(data)} pages)")
                    return self._update_document_metadata(data, original_filename or file_path)

            finally:
                # Clean up temporary file
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)

        except Exception as e:
            logger.error(f"Error loading extractable PDF {file_path}: {str(e)}")
            raise
    
    async def load_docx(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Load DOCX file using PyMuPDFLoader (async)
        Automatically compresses DOCX if larger than 10MB

        Args:
            file_path: Path to DOCX file

        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)

            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)

            # Always attempt compression for optimization
            logger.info(f"DOCX file {file_path} is {file_size_mb:.1f}MB, attempting compression...")

            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
                compressed_path = temp_file.name

            try:
                # Attempt compression without size restriction
                compression_success = await self.compress_docx(file_path, compressed_path)

                if compression_success and os.path.exists(compressed_path):
                    compressed_size_mb = self.get_file_size_mb(compressed_path)
                    logger.info(f"DOCX successfully compressed from {file_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")

                    # Load the compressed file
                    data = await self._load_docx_file(compressed_path)
                    return self._update_document_metadata(data, original_filename or file_path)
                else:
                    # Compression failed, load original file
                    logger.info(f"DOCX compression failed, loading original file: {file_path}")
                    data = await self._load_docx_file(file_path)
                    return self._update_document_metadata(data, original_filename or file_path)

            finally:
                # Clean up temporary file
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)

        except Exception as e:
            logger.error(f"Error loading DOCX {file_path}: {str(e)}")
            raise

    async def _load_docx_file(self, file_path: str) -> List[Any]:
        """
        Helper method to load DOCX file with fallback loaders

        Args:
            file_path: Path to DOCX file

        Returns:
            List of loaded document objects
        """
        # Try PyMuPDFLoader first
        try:
            loader = PyMuPDFLoader(file_path)
            data = await loader.aload()
            logger.info(f"Successfully loaded DOCX: {file_path}")
            return data
        except Exception as pymupdf_e:
            logger.warning(f"PyMuPDF failed for DOCX {file_path}: {str(pymupdf_e)}")
            # Fallback to Docx2txtLoader
            loader = Docx2txtLoader(file_path)
            data = await loader.aload()
            logger.info(f"Successfully loaded DOCX with fallback loader: {file_path}")
            return data
    
    async def load_doc(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Load DOC file using PyMuPDFLoader (async)
        Follows same rules as PDF, DOCX, PPTX: allows up to 50MB, attempts compression if > 10MB
        
        Args:
            file_path: Path to DOC file
            
        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)
            
            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)
            
            # Process DOC file directly (no compression available for DOC files)
            logger.info(f"Processing DOC file: {file_path} ({file_size_mb:.1f}MB)")
            loader = PyMuPDFLoader(file_path)
            data = await loader.aload()
            logger.info(f"Successfully loaded DOC: {file_path}")
            return self._update_document_metadata(data, original_filename or file_path)
                
        except Exception as e:
            logger.error(f"Error loading DOC {file_path}: {str(e)}")
            raise
    
    # Other document formats
    async def load_pptx(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Load PowerPoint file using UnstructuredPowerPointLoader (async)
        Automatically compresses PPTX if larger than 10MB
        
        Args:
            file_path: Path to PPTX file
            
        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)
            
            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)
            
            # Always attempt compression for optimization (PPTX is a ZIP archive)
            logger.info(f"PPTX file {file_path} is {file_size_mb:.1f}MB, attempting compression...")
            
            with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as temp_file:
                compressed_path = temp_file.name
            
            try:
                # Use the same compression method as DOCX (both are ZIP archives)
                compression_success = await self.compress_docx(file_path, compressed_path)
                
                if compression_success and os.path.exists(compressed_path):
                    compressed_size_mb = self.get_file_size_mb(compressed_path)
                    logger.info(f"PPTX successfully compressed from {file_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")
                    
                    # Load the compressed file
                    loader = UnstructuredPowerPointLoader(compressed_path)
                    data = await loader.aload()
                    logger.info(f"Successfully loaded compressed PPTX: {file_path}")
                    return self._update_document_metadata(data, original_filename or file_path)
                else:
                    # Compression failed, load original file
                    logger.info(f"PPTX compression failed, loading original file: {file_path}")
                    loader = UnstructuredPowerPointLoader(file_path)
                    data = await loader.aload()
                    logger.info(f"Successfully loaded original PPTX: {file_path}")
                    return self._update_document_metadata(data, original_filename or file_path)
            
            finally:
                # Clean up temporary file
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)
                
        except Exception as e:
            logger.error(f"Error loading PPTX {file_path}: {str(e)}")
            raise
    
    async def load_excel(self, file_path: str, mode: str = "elements") -> List[Any]:
        """
        Load Excel file using UnstructuredExcelLoader (async)
        
        Args:
            file_path: Path to Excel file (.xlsx or .xls)
            mode: Loading mode ("elements" or "single")
            
        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)
            loader = UnstructuredExcelLoader(file_path, mode=mode)
            data = await loader.aload()
            logger.info(f"Successfully loaded Excel: {file_path} ({len(data)} elements)")
            return data
        except Exception as e:
            logger.error(f"Error loading Excel {file_path}: {str(e)}")
            raise
    
    async def load_csv(self, file_path: str) -> List[Any]:
        """
        Load CSV file using CSVLoader (async)
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List of loaded document objects
        """
        try:
            self.validate_file_exists(file_path)
            loader = CSVLoader(file_path=file_path,encoding="utf-8")
            data = await loader.aload()
            logger.info(f"Successfully loaded CSV: {file_path} ({len(data)} rows)")
            return data
        except Exception as e:
            logger.error(f"Error loading CSV {file_path}: {str(e)}")
            raise
    
    # OpenAI API supported audio formats (MP3, WAV)
    async def load_mp3(self, file_path: str) -> str:
        """
        Load and transcribe MP3 file using OpenAI Whisper (async)
        Compresses MP3 files to 25MB if needed, rejects if still over 25MB after compression
        
        Args:
            file_path: Path to MP3 file
            
        Returns:
            Transcribed text as string
        """
        try:
            self.validate_file_exists(file_path)
            
            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)
            logger.info(f"MP3 file {file_path} is {file_size_mb:.1f}MB")
            
            # Always compress MP3 for optimal file size (regardless of current size)
            logger.info(f"Compressing MP3 file to optimize size...")
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                compressed_path = temp_file.name
            
            try:
                # Attempt compression to 25MB
                compression_success = await self.compress_audio_to_target_size(file_path, compressed_path, target_size_mb=25)
                
                if compression_success:
                    compressed_size_mb = self.get_file_size_mb(compressed_path)
                    logger.info(f"MP3 successfully compressed from {file_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")
                    
                    # Check if final compressed file is ≤ 25MB
                    if compressed_size_mb <= 25:
                        # Transcribe the compressed file
                        result = await self._speech_to_text_api(compressed_path, "audio/mp3")
                        logger.info(f"Successfully transcribed compressed MP3: {file_path}")
                        return result
                    else:
                        # File still too large after compression, reject it
                        error_msg = f"MP3 file remains too large after compression. Original: {file_size_mb:.1f}MB, Compressed: {compressed_size_mb:.1f}MB (>25MB). File rejected."
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                else:
                    # Compression failed, reject it
                    error_msg = f"MP3 file compression failed. Original: {file_size_mb:.1f}MB. File rejected."
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            finally:
                # Clean up temporary file
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)
                
        except Exception as e:
            logger.error(f"Error loading MP3 {file_path}: {str(e)}")
            raise
    
    async def load_wav(self, file_path: str) -> str:
        """
        Load and transcribe WAV file using OpenAI Whisper (async)
        WAV files are first converted to MP3, then compressed to 25MB if needed.
        Files that remain over 25MB after compression are rejected.
        
        Args:
            file_path: Path to WAV file
            
        Returns:
            Transcribed text as string
        """
        try:
            self.validate_file_exists(file_path)
            
            # Check file size
            file_size_mb = self.get_file_size_mb(file_path)
            logger.info(f"WAV file {file_path} is {file_size_mb:.1f}MB")
            
            # Step 1: Convert WAV to MP3
            logger.info(f"Converting WAV file to MP3...")
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_mp3_file:
                mp3_path = temp_mp3_file.name
            
            try:
                # Convert WAV to MP3 using ffmpeg
                conversion_success = await self.convert_wav_to_mp3(file_path, mp3_path)
                
                if not conversion_success:
                    # Conversion failed, reject the file
                    error_msg = f"WAV to MP3 conversion failed for {file_path}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                mp3_size_mb = self.get_file_size_mb(mp3_path)
                logger.info(f"WAV successfully converted to MP3: {file_size_mb:.1f}MB -> {mp3_size_mb:.1f}MB")
                
                # Step 2: Always compress the MP3 (regardless of current size for optimal compression)
                logger.info(f"Compressing converted MP3 to optimize size...")
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_compressed_file:
                    compressed_path = temp_compressed_file.name
                
                try:
                    # Step 3: Compress MP3 to 25MB
                    compression_success = await self.compress_audio_to_target_size(mp3_path, compressed_path, target_size_mb=25)
                    
                    if compression_success:
                        compressed_size_mb = self.get_file_size_mb(compressed_path)
                        logger.info(f"MP3 successfully compressed from {mp3_size_mb:.1f}MB to {compressed_size_mb:.1f}MB")
                        
                        # Step 4: Check if final compressed file is ≤ 25MB
                        if compressed_size_mb <= 25:
                            # Transcribe the compressed MP3 file
                            result = await self._speech_to_text_api(compressed_path, "audio/mp3")
                            logger.info(f"Successfully transcribed compressed WAV->MP3: {file_path}")
                            return result
                        else:
                            # File still too large after compression, reject it
                            error_msg = f"WAV file remains too large after compression. Original WAV: {file_size_mb:.1f}MB, MP3: {mp3_size_mb:.1f}MB, Compressed: {compressed_size_mb:.1f}MB (>25MB). File rejected."
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    else:
                        # Compression failed, reject it
                        error_msg = f"WAV to MP3 compression failed. Original WAV: {file_size_mb:.1f}MB, MP3: {mp3_size_mb:.1f}MB. File rejected."
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                
                finally:
                    # Clean up compressed temporary file
                    if os.path.exists(compressed_path):
                        os.unlink(compressed_path)
            
            finally:
                # Clean up MP3 temporary file
                if os.path.exists(mp3_path):
                    os.unlink(mp3_path)
                
        except Exception as e:
            logger.error(f"Error loading WAV {file_path}: {str(e)}")
            raise
    
    async def _speech_to_text_api(self, file_path: str, mime_type: str) -> str:
        """
        Convert speech audio file to text using OpenAI's Whisper model (async)
        
        Args:
            file_path: Path to the audio file
            mime_type: MIME type of the audio file
            
        Returns:
            Transcribed text
        """
        try:
            async with aiofiles.open(file_path, "rb") as audio_file:
                audio_content = await audio_file.read()
            
            # Get filename for proper file handling
            filename = os.path.basename(file_path)
            
            # Use AsyncOpenAI client directly (no need for run_in_executor)
            transcription = await self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=(filename, audio_content, mime_type)
            )
            
            logger.info(f"Successfully transcribed audio from {file_path}")
            return transcription.text
        except Exception as e:
            logger.error(f"Error in speech-to-text conversion for {file_path}: {str(e)}")
            raise

    async def _openrouter_ocr_scan(self, file_path: str, original_filename: str = None, max_retries: int = 2) -> List[Any]:
        """
        Scan PDF using OpenRouter OCR with enhanced error handling and retries
        
        Args:
            file_path: Path to the PDF file to scan
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of document objects with page content
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if not self.openrouter_api_key:
                    raise ValueError("OPENROUTER_API_KEY is required for OCR scanning")
                
                logger.info(f"OCR attempt {attempt + 1}/{max_retries + 1} for {file_path}")
                
                return await self._perform_ocr_request(file_path, original_filename)
                
            except Exception as e:
                last_error = e
                logger.warning(f"OCR attempt {attempt + 1} failed for {file_path}: {str(e)}")
                
                if attempt < max_retries:
                    logger.info(f"Retrying OCR for {file_path}...")
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"All OCR attempts failed for {file_path}")
                    break
        
        # If all retries failed, raise the last error
        if last_error:
            raise last_error
        else:
            raise ValueError(f"OCR failed for unknown reason: {file_path}")

    async def _perform_ocr_request(self, file_path: str, original_filename: str = None) -> List[Any]:
        """
        Perform the actual OCR request to OpenRouter
        
        Args:
            file_path: Path to the PDF file to scan
            
        Returns:
            List of document objects with page content
        """
        try:
            # Read and encode PDF to Base64
            with open(file_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            
            # Enhanced prompt with better JSON guidance and examples
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": """You are a precision OCR and text extraction specialist. Your task is to extract text from the PDF and return it as valid JSON.

## CRITICAL: JSON OUTPUT ONLY
- Start your response with `[` (first character)
- End your response with `]` (last character)  
- NO explanatory text, NO markdown, NO code blocks
- Your entire response must be valid JSON that can be parsed by json.loads()

## TEXT EXTRACTION RULES:
1. Extract ALL text from every page in reading order
2. Remove page numbers, headers, footers, and watermarks
3. Preserve paragraph structure but remove unnecessary line breaks
4. Keep Arabic text intact with all diacritics and punctuation
5. Escape special characters properly for JSON (quotes, backslashes, newlines)
6. Do not summarize - extract complete content

## EXACT JSON FORMAT REQUIRED:
[
  {
    "page_content": "Complete extracted text from page 1. Make sure to escape quotes with \\" and newlines with \\n"
  },
  {
    "page_content": "Complete extracted text from page 2. All text must be properly escaped for JSON."
  }
]

## JSON ESCAPING EXAMPLES:
- Quotes: "He said \\"Hello\\"" 
- Newlines: "First line\\nSecond line"
- Backslashes: "Path\\\\to\\\\file"

## EXAMPLE OF CORRECT RESPONSE:
[{"page_content": "This is page 1 text with \\"quotes\\" and\\nnewlines properly escaped."},{"page_content": "This is page 2 text."}]

## VALIDATION:
1. Response must start with `[`
2. Response must end with `]`
3. Must be valid JSON (test with json.loads)
4. No extra text outside the JSON array

Extract text now. Return ONLY the JSON array:"""},
                        {"type": "file", "file": {
                            "filename": os.path.basename(file_path),
                            "file_data": f"data:application/pdf;base64,{pdf_base64}"
                        }}
                    ]
                }
            ]
            
            # Specify OCR engine for scanned PDFs - exact from test.py
            plugins = [
                {"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}
            ]
            
            payload = {
                "model": "google/gemini-2.5-pro",  # Gemini via OpenRouter
                "messages": messages,
                "plugins": plugins
            }
            
            # Make async request
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"OpenRouter OCR failed: {response.status_code} - {response.text}")
                raise ValueError(f"OpenRouter OCR request failed: {response.status_code}")
            
            response_data = response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Clean and parse the JSON response with multiple fallback strategies
            try:
                content_list = self._parse_ocr_response(content, file_path)
                
                # Convert to document objects format
                documents = []
                for i, page_data in enumerate(content_list):
                    page_content = page_data.get("page_content", "")
                    # Create a document-like object
                    doc = type('Document', (), {
                        'page_content': page_content,
                        'metadata': {'page': i + 1, 'source': original_filename or file_path, 'extraction_method': 'openrouter_ocr'}
                    })()
                    documents.append(doc)
                
                logger.info(f"Successfully OCR scanned PDF: {file_path} ({len(documents)} pages)")
                return documents
                
            except Exception as parse_error:
                logger.error(f"Failed to parse OpenRouter OCR response: {parse_error}")
                logger.error(f"Raw response content (first 1000 chars): {content[:1000]}")
                raise ValueError(f"Unable to parse OpenRouter OCR response: {parse_error}")
                
        except Exception as e:
            logger.error(f"Error in OpenRouter OCR scan for {file_path}: {str(e)}")
            raise

    def _parse_ocr_response(self, content: str, file_path: str) -> List[dict]:
        """
        Parse OpenRouter OCR response with multiple fallback strategies
        
        Args:
            content: Raw response content from OpenRouter
            file_path: Path to PDF for logging
            
        Returns:
            List of page content dictionaries
        """
        # Strategy 1: Direct JSON parsing
        try:
            content_list = json.loads(content)
            if isinstance(content_list, list) and all(isinstance(item, dict) and 'page_content' in item for item in content_list):
                logger.info(f"Strategy 1 (Direct JSON) successful for {file_path}")
                return content_list
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Clean and trim the response
        try:
            # Remove leading/trailing whitespace and potential markdown
            cleaned_content = content.strip()
            
            # Remove potential markdown code blocks
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith('```'):
                cleaned_content = cleaned_content[3:]
            
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3]
            
            # Find the JSON array boundaries
            start_idx = cleaned_content.find('[')
            end_idx = cleaned_content.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_part = cleaned_content[start_idx:end_idx + 1]
                content_list = json.loads(json_part)
                
                if isinstance(content_list, list) and all(isinstance(item, dict) and 'page_content' in item for item in content_list):
                    logger.info(f"Strategy 2 (Cleaned JSON) successful for {file_path}")
                    return content_list
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Strategy 3: Extract JSON from mixed content
        try:
            # Look for JSON array pattern in the response
            json_pattern = r'\[(?:[^[\]]*(?:\[[^\]]*\][^[\]]*)*)*\]'
            json_matches = re.findall(json_pattern, content, re.DOTALL)
            
            for match in json_matches:
                try:
                    content_list = json.loads(match)
                    if isinstance(content_list, list) and all(isinstance(item, dict) and 'page_content' in item for item in content_list):
                        logger.info(f"Strategy 3 (RegEx extraction) successful for {file_path}")
                        return content_list
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        
        # Strategy 4: Parse line by line for partial JSON
        try:
            lines = content.split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('['):
                    in_json = True
                    json_lines.append(line)
                elif in_json:
                    json_lines.append(line)
                    if line.endswith(']'):
                        break
            
            if json_lines:
                json_text = '\n'.join(json_lines)
                content_list = json.loads(json_text)
                
                if isinstance(content_list, list) and all(isinstance(item, dict) and 'page_content' in item for item in content_list):
                    logger.info(f"Strategy 4 (Line-by-line) successful for {file_path}")
                    return content_list
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Strategy 5: Create fallback structure from raw text
        try:
            # If all JSON parsing fails, treat the entire content as one page
            logger.warning(f"All JSON parsing strategies failed for {file_path}, creating fallback structure")
            
            # Remove potential JSON markers and clean the text
            cleaned_text = content.strip()
            
            # Remove common prefixes/suffixes that might be added by the model
            prefixes_to_remove = ['```json', '```', 'json', 'here is the result:', 'result:', '[', 'Here is the extracted text:']
            suffixes_to_remove = ['```', ']']
            
            for prefix in prefixes_to_remove:
                if cleaned_text.lower().startswith(prefix.lower()):
                    cleaned_text = cleaned_text[len(prefix):].strip()
            
            for suffix in suffixes_to_remove:
                if cleaned_text.endswith(suffix):
                    cleaned_text = cleaned_text[:-len(suffix)].strip()
            
            # Create a single page structure
            fallback_content = [{
                "page_content": cleaned_text
            }]
            
            logger.info(f"Strategy 5 (Fallback) used for {file_path} - treating as single page")
            return fallback_content
            
        except Exception as fallback_error:
            logger.error(f"Even fallback strategy failed for {file_path}: {fallback_error}")
            raise ValueError(f"All parsing strategies failed. Content preview: {content[:200]}...")
    
    # Main loading method
    async def load_file(self, file_path: str, original_filename: str = None, **kwargs) -> Union[List[Any], str]:
        """
        Universal async file loader - automatically detects file type and loads accordingly
        
        Args:
            file_path: Path to the file
            original_filename: Original filename to use in metadata (optional)
            **kwargs: Additional arguments for specific loaders
            
        Returns:
            Loaded data (List for documents, str for audio transcriptions)
        """
        try:
            extension = self.get_file_extension(file_path)
            
            if extension not in self.supported_extensions:
                raise ValueError(f"Unsupported file type: {extension}")
            
            loader_func = self.supported_extensions[extension]
            
            # All functions are now async
            # Pass original_filename for document types that support it
            if extension in {'.pdf', '.docx', '.doc', '.pptx'}:
                return await loader_func(file_path, original_filename=original_filename, **kwargs)
            else:
                return await loader_func(file_path, **kwargs)
                
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise
    
    # Convenience method for loading multiple files concurrently
    async def load_files(self, file_paths: List[str], **kwargs) -> List[Union[List[Any], str]]:
        """
        Load multiple files concurrently
        
        Args:
            file_paths: List of file paths to load
            **kwargs: Additional arguments for specific loaders
            
        Returns:
            List of loaded data for each file
        """
        try:
            tasks = [self.load_file(file_path, **kwargs) for file_path in file_paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions but return successful results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to load {file_paths[i]}: {str(result)}")
            
            return results
        except Exception as e:
            logger.error(f"Error in batch loading: {str(e)}")
            raise
    
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported file formats
        
        Returns:
            List of supported file extensions
        """
        return list(self.supported_extensions.keys())


class PDFScanDetector:
    """
    Comprehensive PDF scan detection with multiple methods
    """
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.results = {}
    
    def method1_text_extraction_ratio(self) -> dict:
        """
        Method 1: Check text extraction ratio
        If very little text is extracted, likely scanned
        """
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_chars = 0
                total_pages = len(pdf_reader.pages)
                
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    total_chars += len(text.strip())
                
                avg_chars_per_page = total_chars / total_pages if total_pages > 0 else 0
                
                # Thresholds based on experience
                if avg_chars_per_page < 50:
                    classification = "SCANNED"
                elif avg_chars_per_page > 500:
                    classification = "EXTRACTABLE"
                else:
                    classification = "MIXED/UNCERTAIN"
                
                return {
                    "method": "Text Extraction Ratio",
                    "total_chars": total_chars,
                    "total_pages": total_pages,
                    "avg_chars_per_page": avg_chars_per_page,
                    "classification": classification,
                    "confidence": "HIGH" if avg_chars_per_page < 50 or avg_chars_per_page > 500 else "MEDIUM"
                }
        except Exception as e:
            return {"method": "Text Extraction Ratio", "error": str(e)}
    
    def method2_image_to_text_ratio(self) -> dict:
        """
        Method 2: Check image-to-text ratio using PyMuPDF
        High image content usually indicates scanned PDF
        """
        try:
            doc = fitz.open(self.pdf_path)
            total_image_area = 0
            total_text_blocks = 0
            total_images = 0
            total_page_area = 0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_rect = page.rect
                total_page_area += page_rect.width * page_rect.height
                
                # Count images
                image_list = page.get_images()
                total_images += len(image_list)
                
                # Calculate image area
                for img in image_list:
                    try:
                        img_rect = page.get_image_rects(img[0])
                        for rect in img_rect:
                            total_image_area += rect.width * rect.height
                    except:
                        pass
                
                # Count text blocks
                text_dict = page.get_text("dict")
                for block in text_dict["blocks"]:
                    if "lines" in block:  # Text block
                        total_text_blocks += 1
            
            image_coverage = (total_image_area / total_page_area) * 100 if total_page_area > 0 else 0
            
            if image_coverage > 80 and total_text_blocks < 5:
                classification = "SCANNED"
            elif image_coverage < 20 and total_text_blocks > 10:
                classification = "EXTRACTABLE"
            else:
                classification = "MIXED/UNCERTAIN"
            
            doc.close()
            
            return {
                "method": "Image-to-Text Ratio",
                "total_images": total_images,
                "image_coverage_percent": round(image_coverage, 2),
                "total_text_blocks": total_text_blocks,
                "classification": classification,
                "confidence": "HIGH" if image_coverage > 80 or image_coverage < 20 else "MEDIUM"
            }
        except Exception as e:
            return {"method": "Image-to-Text Ratio", "error": str(e)}
    
    def method3_font_analysis(self) -> dict:
        """
        Method 3: Analyze fonts in PDF
        Scanned PDFs typically have no fonts or very few fonts
        """
        try:
            doc = fitz.open(self.pdf_path)
            all_fonts = set()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                font_list = page.get_fonts()
                for font in font_list:
                    all_fonts.add(font[3])  # Font name
            
            font_count = len(all_fonts)
            
            if font_count == 0:
                classification = "SCANNED"
                confidence = "HIGH"
            elif font_count < 3:
                classification = "LIKELY_SCANNED"
                confidence = "MEDIUM"
            else:
                classification = "EXTRACTABLE"
                confidence = "HIGH"
            
            doc.close()
            
            return {
                "method": "Font Analysis",
                "font_count": font_count,
                "fonts_found": list(all_fonts),
                "classification": classification,
                "confidence": confidence
            }
        except Exception as e:
            return {"method": "Font Analysis", "error": str(e)}
    
    def method4_pdfplumber_analysis(self) -> dict:
        """
        Method 4: Use pdfplumber for detailed text analysis
        """
        try:
            extractable_text_ratio = 0
            total_pages = 0
            
            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                pages_with_text = 0
                total_chars = 0
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text and len(text.strip()) > 20:
                        pages_with_text += 1
                        total_chars += len(text.strip())
                
                extractable_text_ratio = (pages_with_text / total_pages) * 100 if total_pages > 0 else 0
                avg_chars_per_page = total_chars / total_pages if total_pages > 0 else 0
            
            if extractable_text_ratio > 90 and avg_chars_per_page > 200:
                classification = "EXTRACTABLE"
                confidence = "HIGH"
            elif extractable_text_ratio < 10 or avg_chars_per_page < 50:
                classification = "SCANNED"
                confidence = "HIGH"
            else:
                classification = "MIXED"
                confidence = "MEDIUM"
            
            return {
                "method": "PDFPlumber Analysis",
                "total_pages": total_pages,
                "pages_with_text": pages_with_text,
                "extractable_text_ratio": round(extractable_text_ratio, 2),
                "avg_chars_per_page": round(avg_chars_per_page, 2),
                "classification": classification,
                "confidence": confidence
            }
        except Exception as e:
            return {"method": "PDFPlumber Analysis", "error": str(e)}
    
    def method5_file_size_analysis(self) -> dict:
        """
        Method 5: Analyze file size patterns
        Scanned PDFs are typically much larger due to image content
        """
        try:
            file_size_mb = os.path.getsize(self.pdf_path) / (1024 * 1024)
            
            # Get page count for size-per-page ratio
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
            
            size_per_page_mb = file_size_mb / total_pages if total_pages > 0 else file_size_mb
            
            # Typical patterns (these are rough guidelines)
            if size_per_page_mb > 1.0:  # More than 1MB per page
                classification = "LIKELY_SCANNED"
                confidence = "MEDIUM"
            elif size_per_page_mb < 0.1:  # Less than 100KB per page
                classification = "LIKELY_EXTRACTABLE"
                confidence = "MEDIUM"
            else:
                classification = "UNCERTAIN"
                confidence = "LOW"
            
            return {
                "method": "File Size Analysis",
                "total_size_mb": round(file_size_mb, 2),
                "total_pages": total_pages,
                "size_per_page_mb": round(size_per_page_mb, 3),
                "classification": classification,
                "confidence": confidence
            }
        except Exception as e:
            return {"method": "File Size Analysis", "error": str(e)}
    
    def comprehensive_analysis(self) -> dict:
        """
        Run all detection methods and provide a comprehensive result
        """
        methods = [
            self.method1_text_extraction_ratio,
            self.method2_image_to_text_ratio,
            self.method3_font_analysis,
            self.method4_pdfplumber_analysis,
            self.method5_file_size_analysis
        ]
        
        results = []
        scanned_votes = 0
        extractable_votes = 0
        
        for method in methods:
            result = method()
            results.append(result)
            
            if 'classification' in result:
                classification = result['classification']
                if 'SCANNED' in classification:
                    scanned_votes += 2 if result.get('confidence') == 'HIGH' else 1
                elif 'EXTRACTABLE' in classification:
                    extractable_votes += 2 if result.get('confidence') == 'HIGH' else 1
        
        # Final determination
        if scanned_votes > extractable_votes * 1.5:
            final_classification = "SCANNED"
            recommendation = "Use OCR for text extraction"
        elif extractable_votes > scanned_votes * 1.5:
            final_classification = "EXTRACTABLE"
            recommendation = "Use standard PDF text extraction"
        else:
            final_classification = "MIXED"
            recommendation = "Try text extraction first, use OCR for failed pages"
        
        return {
            "pdf_path": self.pdf_path,
            "final_classification": final_classification,
            "recommendation": recommendation,
            "scanned_votes": scanned_votes,
            "extractable_votes": extractable_votes,
            "detailed_results": results
        }


def analyze_pdf(pdf_path: str):
    """
    Simple function to analyze a PDF and determine if it's scanned
    """
    detector = PDFScanDetector(pdf_path)
    return detector.comprehensive_analysis()


# # Usage Examples
# async def main():
#     """Example usage of the async UniversalFileLoader"""
#     # Initialize the loader
#     loader = UniversalFileLoader()  # OpenAI API key from environment
#     # Or with explicit API key: loader = UniversalFileLoader(openai_api_key="your-key-here")
    
#     try:
#         # Load single files
#         pdf_data = await loader.load_file("path/to/document.pdf")
#         print(f"PDF loaded: {len(pdf_data)} pages")
        
#         # Load Excel with custom mode
#         excel_data = await loader.load_file("path/to/spreadsheet.xlsx", mode="elements")
#         print(f"Excel loaded: {len(excel_data)} elements")
        
#         # Load CSV
#         csv_data = await loader.load_file("path/to/data.csv")
#         print(f"CSV loaded: {len(csv_data)} rows")
        
#         # Load PowerPoint
#         pptx_data = await loader.load_file("path/to/presentation.pptx")
#         print(f"PPTX loaded: {len(pptx_data)} elements")
        
#         # Load Word documents
#         docx_data = await loader.load_file("path/to/document.docx")
#         doc_data = await loader.load_file("path/to/document.doc")
        
#         # Load audio files
#         mp3_transcript = await loader.load_file("path/to/audio.mp3")
#         wav_transcript = await loader.load_file("path/to/audio.wav")
#         print(f"Audio transcripts: {len(mp3_transcript)} characters")
        
#         # Load multiple files concurrently (NEW FEATURE!)
#         file_paths = [
#             "path/to/document1.pdf",
#             "path/to/document2.docx",
#             "path/to/audio.mp3",
#             "path/to/data.csv"
#         ]
#         results = await loader.load_files(file_paths)
#         print(f"Loaded {len([r for r in results if not isinstance(r, Exception)])} files successfully")
        
#         # Check supported formats
#         print("Supported formats:", loader.get_supported_formats())
        
#     except Exception as e:
#         print(f"Error: {e}")


# # Synchronous wrapper for backward compatibility
# def load_file_sync(file_path: str, openai_api_key: str = None, **kwargs) -> Union[List[Any], str]:
#     """
#     Synchronous wrapper for the async load_file method
    
#     Args:
#         file_path: Path to the file
#         openai_api_key: OpenAI API key (optional)
#         **kwargs: Additional arguments for specific loaders
        
#     Returns:
#         Loaded data
#     """
#     async def _load():
#         loader = UniversalFileLoader(openai_api_key=openai_api_key)
#         return await loader.load_file(file_path, **kwargs)
    
#     return asyncio.run(_load())


# if __name__ == "__main__":
#     # Run the async main function
#     asyncio.run(main())
    
#     # Or use the synchronous wrapper
#     # data = load_file_sync("path/to/file.pdf")