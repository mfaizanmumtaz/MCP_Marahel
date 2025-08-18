from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
import logging
import os
import asyncio


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture detailed logs
formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)
log_dir = os.path.join("..", "log", "ai")
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(os.path.join(log_dir, "arabic_bot_utils.log"))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class IncomingFileProcessor:
    def __init__(self, chunk_size, chunk_overlap) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info(
            f"Initialized IncomingFileProcessor with chunk_size: {chunk_size} and chunk_overlap: {chunk_overlap}"
        )
        self.textsplit = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )

    async def get_docx_splits(self, docx_file: str, file_original_name: str):
        try:
            logger.info(f"Processing DOCX file: {file_original_name}")
            loop = asyncio.get_event_loop()
            loader = PyMuPDFLoader(str(docx_file))
            pages = await loop.run_in_executor(None, loader.load)
            logger.debug(
                f"Loaded {len(pages)} pages from DOCX file: {file_original_name}"
            )

            doc_list = await loop.run_in_executor(
                None, lambda: self.textsplit.split_documents(pages)
            )
            logger.debug(f"Split DOCX file into {len(doc_list)} chunks.")

            page_content_map = {}
            for text in doc_list:
                page_num = text.metadata.get("page", 1) + 1  # increment with one
                page_content_map.setdefault(page_num, []).append(text.page_content)

            final_docs = []
            for page_num, contents in page_content_map.items():
                combined_content = "\n".join(contents)
                final_docs.append(
                    Document(
                        page_content=combined_content,
                        metadata={"source": file_original_name, "page": page_num},
                    )
                )

            logger.info(f"Successfully split DOCX into {len(final_docs)} documents")
            return final_docs
        except Exception as ex:
            logger.error(f"Error processing DOCX file {file_original_name}: {str(ex)}")
            raise

    async def get_pdf_splits(self, pdf_file: str, file_original_name: str):
        try:
            logger.info(f"Processing PDF file: {file_original_name}")
            loop = asyncio.get_event_loop()
            loader = PyPDFLoader(pdf_file)
            pages = await loop.run_in_executor(None, loader.load)
            logger.debug(
                f"Loaded {len(pages)} pages from PDF file: {file_original_name}"
            )

            doc_list = await loop.run_in_executor(
                None, lambda: self.textsplit.split_documents(pages)
            )
            logger.debug(f"Split PDF file into {len(doc_list)} chunks.")

            page_content_map = {}
            for text in doc_list:
                page_num = text.metadata.get("page", 1) + 1  # increment with one
                page_content_map.setdefault(page_num, []).append(text.page_content)

            final_docs = []
            for page_num, contents in page_content_map.items():
                combined_content = "\n".join(contents)
                final_docs.append(
                    Document(
                        page_content=combined_content,
                        metadata={"source": file_original_name, "page": page_num},
                    )
                )

            logger.info(f"Successfully split PDF into {len(final_docs)} documents")
            return final_docs
        except Exception as ex:
            logger.error(f"Error processing PDF file {file_original_name}: {str(ex)}")
            raise

    async def get_doc_splits(self, doc_file: str, file_original_name: str):
        try:
            logger.info(f"Processing DOC file: {file_original_name}")
            loop = asyncio.get_event_loop()
            loader = PyMuPDFLoader(str(doc_file))
            pages = await loop.run_in_executor(None, loader.load)
            logger.debug(
                f"Loaded {len(pages)} pages from DOC file: {file_original_name}"
            )

            doc_list = await loop.run_in_executor(
                None, lambda: self.textsplit.split_documents(pages)
            )
            logger.debug(f"Split DOC file into {len(doc_list)} chunks.")

            page_content_map = {}
            for text in doc_list:
                page_num = text.metadata.get("page", 1) + 1  # increment with one
                page_content_map.setdefault(page_num, []).append(text.page_content)

            final_docs = []
            for page_num, contents in page_content_map.items():
                combined_content = "\n".join(contents)
                final_docs.append(
                    Document(
                        page_content=combined_content,
                        metadata={"source": file_original_name, "page": page_num},
                    )
                )

            logger.info(f"Successfully split DOC into {len(final_docs)} documents")
            return final_docs
        except Exception as ex:
            logger.error(f"Error processing DOC file {file_original_name}: {str(ex)}")
            raise
