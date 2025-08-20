import asyncio
import json
import os
import logging
import base64
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import PyPDF2
from io import BytesIO
import aiofiles
import httpx
import ast
import nest_asyncio
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())

nest_asyncio.apply()
# ------------------------ Logging ------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ocr_async")

# ------------------------ Class --------------------------
class OCRAccuracyTester:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        request_timeout: float = 60.0,
        download_timeout: float = 30.0,
        max_concurrency: int = 3,
        max_retries: int = 3,
        backoff_initial: float = 1.0,
        rate_limit_delay: float = 0.0,  # optional per-request delay (seconds)
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.request_timeout = request_timeout
        self.download_timeout = download_timeout
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_retries = max_retries
        self.backoff_initial = backoff_initial
        self.rate_limit_delay = rate_limit_delay

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # System prompt (kept from your original)
        self.system_prompt = """You are a precision OCR and text extraction specialist. Your task is to extract ALL text from the PDF document.

## TEXT EXTRACTION RULES:
1. Extract ALL visible text from every page in reading order
2. Maintain paragraph structure and line breaks where they make sense
3. Remove repetitive page numbers, headers, footers, and watermarks
4. Keep all languages intact (Arabic, English, etc.) with proper diacritics and punctuation
5. Include mathematical formulas, equations, and symbols as text
6. Do not summarize or paraphrase - extract the complete original content
7. If there are multiple columns, read left to right, top to bottom
8. Include table contents in a readable format

## RESPONSE FORMAT:
Return the text as a simple Python list of strings, where each string contains the complete text from one page.

Format like this:
[
"Complete text from page 1...",
"Complete text from page 2...",
"Complete text from page 3..."
]

Important:
- Each string in the list = one page of content
- Include ALL text from each page
- Use proper Python list syntax with quotes
- No extra formatting, just the list

Extract all text from this PDF document:"""

        # Model configurations (preserved)
        self.models: Dict[str, Dict[str, Any]] = {
            "mistral-ocr": {
                "name": "mistral-ocr",
                "use_plugin": True,
                "plugin_engine": "mistral-ocr",
                "follow_up_model": "google/gemini-2.5-flash",
            },
            "gemini-pro": {"name": "google/gemini-2.5-pro", "use_plugin": False},
            "claude-sonnet": {"name": "anthropic/claude-sonnet-4", "use_plugin": False},
        }

        self.results: List[Dict[str, Any]] = []
        self._client: Optional[httpx.AsyncClient] = None
        self._dl_client: Optional[httpx.AsyncClient] = None

    # ---------- Async context to own the client ----------
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.request_timeout)
        self._dl_client = httpx.AsyncClient(timeout=self.download_timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            await self._client.aclose()
        if self._dl_client:
            await self._dl_client.aclose()

    # ----------------- File helpers (async) ----------------
    async def download_pdf(self, url: str, local_path: str) -> bool:
        try:
            assert self._dl_client is not None, "HTTP client not initialized"
            logger.info(f"Downloading PDF from {url}")
            async with self._dl_client.stream("GET", url) as response:
                response.raise_for_status()
                async with aiofiles.open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
            logger.info(f"PDF downloaded successfully to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            return False

    async def read_pdf_file(self, file_path: str) -> bytes:
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"PDF file not found: {file_path}")
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read PDF from {file_path}: {e}")
            raise

    @staticmethod
    def encode_pdf_to_base64(pdf_bytes: bytes) -> str:
        return base64.b64encode(pdf_bytes).decode("utf-8")

    @staticmethod
    def _get_pdf_page_count_sync(pdf_bytes: bytes) -> int:
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            return len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return 0

    async def get_pdf_page_count(self, pdf_bytes: bytes) -> int:
        # offload PyPDF2 to a thread so we don't block the loop
        return await asyncio.to_thread(self._get_pdf_page_count_sync, pdf_bytes)

    # --------------- HTTP + retries (async) ----------------
    async def _post_json_with_retries(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(payload)
        assert self._client is not None, "HTTP client not initialized"
        attempt = 0
        backoff = self.backoff_initial

        while True:
            try:
                async with self.semaphore:
                    if self.rate_limit_delay > 0:
                        await asyncio.sleep(self.rate_limit_delay)
                    resp = await self._client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                attempt += 1
                if attempt > self.max_retries:
                    logger.error(f"API request failed after {self.max_retries} retries: {e}")
                    return {"error": str(e)}
                logger.warning(f"API request error (attempt {attempt}/{self.max_retries}): {e}. "
                               f"Retrying in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff *= 2

    # ------------------- OpenRouter call -------------------
    async def make_api_request(
        self,
        model_config: Dict[str, Any],
        pdf_path: str,
        pdf_bytes: bytes,
        *,
        page_specific: bool = False,
        page_num: Optional[int] = None,
    ) -> Dict[str, Any]:

        text_prompt = (f"Extract text from page {page_num} of this PDF document."
                       if page_specific and page_num is not None
                       else "Extract text from this PDF document.")

        pdf_base64 = self.encode_pdf_to_base64(pdf_bytes)

        messages: List[Dict[str, Any]] = [
            # {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.system_prompt},
                    {
                        "type": "file",
                        "file": {
                            "filename": os.path.basename(pdf_path),
                            "file_data": f"data:application/pdf;base64,{pdf_base64}",
                        },
                    },
                ],
            },
        ]

        payload: Dict[str, Any] = {"messages": messages, "temperature": 0}

        if model_config["name"] == "mistral-ocr":
            payload["model"] = model_config["follow_up_model"]
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
        else:
            payload["model"] = model_config["name"]

        return await self._post_json_with_retries(self.base_url, payload)

    # ------------------- Parsing helpers -------------------
    def _parse_ocr_response(
        self, content: str, file_path: str = "", page_num: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            cleaned = content.strip()

            # Strip markdown fences if any
            if cleaned.startswith("```") and cleaned.endswith("```"):
                lines = cleaned.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            # Try Python literal list
            try:
                page_texts = ast.literal_eval(cleaned)
                if isinstance(page_texts, list):
                    docs = []
                    for i, page_text in enumerate(page_texts):
                        if isinstance(page_text, str):
                            docs.append(
                                {"page_content": page_text, "page_number": i + 1, "source": file_path}
                            )
                    if docs:
                        return docs
            except Exception:
                pass

            # Try JSON list
            try:
                page_texts = json.loads(cleaned)
                if isinstance(page_texts, list):
                    docs = []
                    for i, page_text in enumerate(page_texts):
                        if isinstance(page_text, str):
                            docs.append(
                                {"page_content": page_text, "page_number": i + 1, "source": file_path}
                            )
                    if docs:
                        return docs
            except Exception:
                pass

            # Fallback: single page
            if page_num is not None:
                return [{"page_content": cleaned, "page_number": page_num, "source": file_path}]
            else:
                return [{"page_content": cleaned, "page_number": 1, "source": file_path}]

        except Exception as e:
            logger.error(f"Error parsing OCR response: {e}")
            return [
                {"page_content": content, "page_number": page_num if page_num else 1, "source": file_path}
            ]

    def validate_response_format(self, response_text: str) -> Tuple[bool, Optional[List[Dict[str, Any]]], str]:
        try:
            if not response_text or response_text.strip() == "":
                return False, None, "Empty response"

            parsed_docs = self._parse_ocr_response(response_text)
            if parsed_docs and any(doc.get("page_content", "").strip() for doc in parsed_docs):
                return True, parsed_docs, f"Valid content with {len(parsed_docs)} page(s)"
            return False, None, "Could not parse any valid pages"
        except Exception as e:
            return False, None, f"Response validation error: {e}"

    def calculate_metrics(
        self, response_data: Dict[str, Any], start_time: float, file_path: str = "", page_num: Optional[int] = None
    ) -> Dict[str, Any]:
        end_time = time.perf_counter()
        metrics = {
            "response_time": round(end_time - start_time, 2),
            "success": "error" not in response_data,
            "content_valid": False,
            "page_count": 0,
            "total_characters": 0,
            "total_words": 0,
            "error_message": None,
            "documents": [],
        }

        if not metrics["success"]:
            metrics["error_message"] = response_data.get("error", "Unknown error")
            return metrics

        try:
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            content_list = self._parse_ocr_response(content, file_path, page_num)
            is_valid = len(content_list) > 0 and all("page_content" in item for item in content_list)
            metrics["content_valid"] = is_valid

            if is_valid:
                metrics["page_count"] = len(content_list)
                total_chars = sum(len(item.get("page_content", "")) for item in content_list)
                total_words = sum(len(item.get("page_content", "").split()) for item in content_list)

                metrics["total_characters"] = total_chars
                metrics["total_words"] = total_words

                # Keep documents as dicts (cleaner than dynamic types)
                docs = []
                for i, page_data in enumerate(content_list):
                    page_content = page_data.get("page_content", "")
                    page_number = page_data.get("page_number", i + 1)
                    docs.append(
                        {
                            "page_content": page_content,
                            "metadata": {
                                "page": page_number,
                                "source": file_path,
                                "extraction_method": "openrouter_ocr",
                                "character_count": len(page_content),
                                "word_count": len(page_content.split()) if page_content else 0,
                            },
                        }
                    )
                metrics["documents"] = docs
            else:
                metrics["error_message"] = "Could not extract valid content from response"

        except Exception as e:
            metrics["error_message"] = f"Error processing response: {e}"

        return metrics

    # -------------------- Test approaches ------------------
    async def test_full_pdf_approach(self, model_key: str, pdf_path: str, pdf_bytes: bytes) -> Dict[str, Any]:
        logger.info(f"Testing {model_key} with full PDF approach")
        model_config = self.models[model_key]
        start_time = time.perf_counter()
        response = await self.make_api_request(model_config, pdf_path, pdf_bytes, page_specific=False)
        metrics = self.calculate_metrics(response, start_time, pdf_path)
        return {"model": model_key, "approach": "full_pdf", "metrics": metrics, "raw_response": response if metrics["success"] else None}

    async def _process_single_page(
        self, model_config: Dict[str, Any], pdf_path: str, pdf_bytes: bytes, page_num: int
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        response = await self.make_api_request(
            model_config, pdf_path, pdf_bytes, page_specific=True, page_num=page_num
        )
        metrics = self.calculate_metrics(response, start_time, f"{pdf_path}#page{page_num}", page_num)
        return {"page": page_num, "metrics": metrics, "raw_response": response if metrics["success"] else None}

    async def test_page_by_page_approach(
        self, model_key: str, pdf_path: str, pdf_bytes: bytes, total_pages: int
    ) -> Dict[str, Any]:
        logger.info(f"Testing {model_key} with page-by-page approach ({total_pages} pages)")
        model_config = self.models[model_key]

        # Run with bounded concurrency (semaphore applies inside requests)
        tasks = [self._process_single_page(model_config, pdf_path, pdf_bytes, p) for p in range(1, total_pages + 1)]
        total_start = time.perf_counter()
        page_results_list: List[Any] = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.perf_counter() - total_start

        # Normalize exceptions
        page_results: List[Dict[str, Any]] = []
        for idx, res in enumerate(page_results_list, start=1):
            if isinstance(res, Exception):
                logger.error(f"Page {idx} failed: {res}")
                page_results.append(
                    {"page": idx, "metrics": {"success": False, "content_valid": False, "error_message": str(res), "total_characters": 0, "total_words": 0, "response_time": 0}, "raw_response": None}
                )
            else:
                page_results.append(res)

        successful_pages = sum(1 for r in page_results if r["metrics"].get("success"))
        valid_content_pages = sum(1 for r in page_results if r["metrics"].get("content_valid"))

        aggregate = {
            "total_response_time": round(total_time, 2),
            "pages_processed": len(page_results),
            "successful_pages": successful_pages,
            "valid_content_pages": valid_content_pages,
            "success_rate": round(successful_pages / len(page_results), 2) if page_results else 0,
            "content_validity_rate": round(valid_content_pages / len(page_results), 2) if page_results else 0,
            "total_characters": sum(r["metrics"].get("total_characters", 0) for r in page_results),
            "total_words": sum(r["metrics"].get("total_words", 0) for r in page_results),
        }

        return {"model": model_key, "approach": "page_by_page", "aggregate_metrics": aggregate, "page_results": page_results}

    # ------------------- Comprehensive test ----------------
    async def run_comprehensive_test(self, pdf_path_or_url: str):
        logger.info("Starting comprehensive OCR accuracy test")
        logger.info(f"PDF Path/URL: {pdf_path_or_url}")

        is_url = pdf_path_or_url.startswith(("http://", "https://"))
        temp_pdf_path: Optional[str] = None

        if is_url:
            temp_pdf_path = f"temp_pdf_{int(time.time())}.pdf"
            ok = await self.download_pdf(pdf_path_or_url, temp_pdf_path)
            if not ok:
                logger.error("Failed to download PDF")
                return
            pdf_path = temp_pdf_path
        else:
            pdf_path = pdf_path_or_url

        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return

        try:
            pdf_bytes = await self.read_pdf_file(pdf_path)
            total_pages = await self.get_pdf_page_count(pdf_bytes)
            logger.info(f"PDF has {total_pages} pages")
            logger.info(f"PDF size: {len(pdf_bytes)} bytes")
        except Exception as e:
            logger.error(f"Failed to analyze PDF: {e}")
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except Exception:
                    pass
            return

        test_start_time = datetime.now()

        # Test models sequentially to be gentle with rate limits
        for model_key in self.models.keys():
            logger.info("\n" + "=" * 50)
            logger.info(f"Testing model: {model_key}")
            logger.info("=" * 50)
            try:
                full_pdf_result = await self.test_full_pdf_approach(model_key, pdf_path, pdf_bytes)
                self.results.append(full_pdf_result)

                # Optional spacing between approaches
                if self.rate_limit_delay:
                    await asyncio.sleep(self.rate_limit_delay)

                page_by_page_result = await self.test_page_by_page_approach(model_key, pdf_path, pdf_bytes, total_pages)
                self.results.append(page_by_page_result)

                if self.rate_limit_delay:
                    await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.error(f"Error testing {model_key}: {e}")
                continue

        # Cleanup temp file
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
                logger.info(f"Cleaned up temporary file: {temp_pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {e}")

        await self.generate_report(test_start_time, pdf_path_or_url, total_pages)

    # -------------------- Reporting ------------------------
    async def generate_report(self, test_start_time: datetime, pdf_path: str, total_pages: int):
        test_end_time = datetime.now()

        report = {
            "test_metadata": {
                "start_time": test_start_time.isoformat(),
                "end_time": test_end_time.isoformat(),
                "duration_minutes": round((test_end_time - test_start_time).total_seconds() / 60, 2),
                "pdf_path": pdf_path,
                "pdf_filename": os.path.basename(pdf_path) if not pdf_path.startswith(("http://", "https://")) else pdf_path,
                "total_pages": total_pages,
            },
            "results": self.results,
            "summary": self.create_summary(),
        }

        filename = f"ocr_test_results_{test_start_time.strftime('%Y%m%d_%H%M%S')}.json"
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            await f.write(json.dumps(report, indent=2, ensure_ascii=False, default=str))

        logger.info(f"Detailed results saved to: {filename}")
        self.print_summary(report)

    def create_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "models_tested": len(self.models),
            "total_tests": len(self.results),
            "by_approach": {"full_pdf": [], "page_by_page": []},
            "success_rates": {},
            "content_validity_rates": {},
            "avg_response_times": {},
            "character_counts": {},
            "word_counts": {},
        }

        for result in self.results:
            approach = result["approach"]
            model = result["model"]
            summary["by_approach"][approach].append(result)

            if approach == "full_pdf":
                metrics = result["metrics"]
                summary["success_rates"][f"{model}_{approach}"] = metrics.get("success", False)
                summary["content_validity_rates"][f"{model}_{approach}"] = metrics.get("content_valid", False)
                summary["avg_response_times"][f"{model}_{approach}"] = metrics.get("response_time", 0)
                summary["character_counts"][f"{model}_{approach}"] = metrics.get("total_characters", 0)
                summary["word_counts"][f"{model}_{approach}"] = metrics.get("total_words", 0)

            elif approach == "page_by_page":
                agg = result["aggregate_metrics"]
                summary["success_rates"][f"{model}_{approach}"] = agg.get("success_rate", 0)
                summary["content_validity_rates"][f"{model}_{approach}"] = agg.get("content_validity_rate", 0)
                summary["avg_response_times"][f"{model}_{approach}"] = agg.get("total_response_time", 0)
                summary["character_counts"][f"{model}_{approach}"] = agg.get("total_characters", 0)
                summary["word_counts"][f"{model}_{approach}"] = agg.get("total_words", 0)

        return summary

    def print_summary(self, report: Dict[str, Any]):
        print("\n" + "=" * 60)
        print("OCR ACCURACY TEST SUMMARY")
        print("=" * 60)
        metadata = report["test_metadata"]
        print(f"Test Duration: {metadata['duration_minutes']} minutes")
        print(f"PDF File: {metadata['pdf_filename']}")
        print(f"PDF Path: {metadata['pdf_path']}")
        print(f"PDF Pages: {metadata['total_pages']}")
        print(f"Models Tested: {len(self.models)}")
        print(f"Total Tests: {len(self.results)}")

        print("\n" + "=" * 60)
        print("RESULTS BY MODEL AND APPROACH")
        print("=" * 60)

        for model_key in self.models.keys():
            print(f"\n{model_key.upper()}:")
            print("-" * 40)

            full_pdf_results = [r for r in self.results if r["model"] == model_key and r["approach"] == "full_pdf"]
            if full_pdf_results:
                m = full_pdf_results[0]["metrics"]
                print("  Full PDF Approach:")
                print(f"    Success: {m.get('success')}")
                print(f"    Content Valid: {m.get('content_valid')}")
                print(f"    Response Time: {m.get('response_time')}s")
                if m.get("page_count"):
                    print(f"    Pages Extracted: {m.get('page_count')}")
                    print(f"    Total Characters: {m.get('total_characters')}")
                    print(f"    Total Words: {m.get('total_words')}")
                if m.get("error_message"):
                    print(f"    Error: {m.get('error_message')}")

            page_results = [r for r in self.results if r["model"] == model_key and r["approach"] == "page_by_page"]
            if page_results:
                agg = page_results[0]["aggregate_metrics"]
                print("  Page-by-Page Approach:")
                print(f"    Success Rate: {agg['success_rate'] * 100}%")
                print(f"    Content Validity Rate: {agg['content_validity_rate'] * 100}%")
                print(f"    Total Time: {agg['total_response_time']}s")
                print(f"    Pages Processed: {agg['pages_processed']}")
                print(f"    Total Characters: {agg['total_characters']}")
                print(f"    Total Words: {agg['total_words']}")

    # --------------------- Batch mode ----------------------
    def get_pdf_files_from_directory(self, directory_path: str, extension: str = ".pdf") -> List[str]:
        if not os.path.exists(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            return []
        pdfs = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if f.lower().endswith(extension.lower())]
        logger.info(f"Found {len(pdfs)} PDF files in {directory_path}")
        return sorted(pdfs)

    async def run_batch_test(self, directory_path: str):
        pdf_files = self.get_pdf_files_from_directory(directory_path)
        if not pdf_files:
            logger.error("No PDF files found in directory")
            return

        logger.info(f"Running batch test on {len(pdf_files)} PDF files")
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info("\n" + "=" * 60)
            logger.info(f"Processing PDF {i}/{len(pdf_files)}: {os.path.basename(pdf_path)}")
            logger.info("=" * 60)
            try:
                await self.run_comprehensive_test(pdf_path)
            except Exception as e:
                logger.error(f"Failed to process {pdf_path}: {e}")
                continue

# ------------------------- Runner -------------------------
async def main():
    API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not API_KEY:
        print("Error: Please set OPENROUTER_API_KEY environment variable")
        print("Example: export OPENROUTER_API_KEY='your_api_key_here'")
        return

    # Example inputs
    PDF_URL = "https://arxiv.org/pdf/1706.03762"
    SAMPLE_DIR = os.path.join("data", "Sample Files for OCR comparison")

    # Tune concurrency/rate-limits here if needed
    async with OCRAccuracyTester(
        API_KEY,
        max_concurrency=3,
        max_retries=3,
        backoff_initial=1.0,
        rate_limit_delay=0.0,  # set e.g. 0.5–1.0s if you hit rate limits
    ) as tester:
        # Single URL:
        # await tester.run_comprehensive_test(PDF_URL)

        # Single local file:
        # await tester.run_comprehensive_test("/path/to/your/file.pdf")

        # Batch directory:
        await tester.run_batch_test(SAMPLE_DIR)

if __name__ == "__main__":
    asyncio.run(main())
