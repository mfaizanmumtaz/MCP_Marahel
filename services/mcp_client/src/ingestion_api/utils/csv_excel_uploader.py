import pandas as pd
import os
import uuid
from typing import Optional
from fastapi import HTTPException
import aiofiles
from ingestion_api.db.models import UserFile
from ingestion_api.db.connection import async_session
from typing import List, Dict
from sqlalchemy import select, delete
from io import BytesIO
from ingestion_api.utils.excel_to_csv_converter import TEMP_DIR


class CSVExcelHandler:
    """Internal module for handling CSV and Excel file uploads to database"""

    ALLOWED_EXTENSIONS = {".csv", ".xlsx"}

    def __init__(self):
        self.table_name = "user_files"
        # Ensure temp directory exists
        os.makedirs(TEMP_DIR, exist_ok=True)

    @staticmethod
    def is_csv_or_excel(filename: str) -> bool:
        """Check if file is CSV or Excel based on extension"""
        _, ext = os.path.splitext(filename)
        return ext.lower() in CSVExcelHandler.ALLOWED_EXTENSIONS

    async def store_file(
        self,
        user_uuid: str,
        session_id: str,
        file_content: bytes,
        original_filename: str,
    ) -> str:
        """
        Store file content in database. Deletes all previous files for the given chatbot_id and session_id
        before inserting the new file.

        Args:
            user_uuid: UUID of the user/chatbot
            session_id: Optional Session ID for the upload
            file_content: Binary content of the file
            original_filename: Original name of the file

        Returns:
            str: Generated file ID
        """

        if not session_id:
            raise HTTPException(
                422, "session_id is required for the exce/csv file ingestion."
            )

        if not self.is_csv_or_excel(original_filename):
            raise ValueError("Only CSV and Excel files are supported")

        file_id = str(uuid.uuid4())

        async with async_session() as session:
            # Delete all previous files for this chatbot_id and session_id
            await session.execute(
                delete(UserFile).where(
                    UserFile.chatbot_id == user_uuid, UserFile.session_id == session_id
                )
            )

            # Create and insert new file
            new_file = UserFile(
                id=file_id,
                chatbot_id=user_uuid,
                filename=original_filename,
                content=file_content,
                session_id=session_id,
            )

            session.add(new_file)
            await session.commit()

        return file_id

    async def process_in_memory(
        self,
        user_uuid: str,
        session_id: str,
        file_content: bytes,
        filename: str,
    ) -> Optional[str]:
        """
        Process file content directly without saving to temp file

        Args:
            user_uuid: UUID of the user/chatbot
            file_content: Binary content of the file
            filename: Original filename

        Returns:
            str: File ID if processed, None if not CSV/Excel
        """
        if not self.is_csv_or_excel(filename):
            return None

        try:
            return await self.store_file(user_uuid, session_id, file_content, filename)
        except Exception as e:
            raise RuntimeError(f"Failed to process file: {str(e)}")

    async def process_from_temp_file(
        self, user_uuid: str, file_path: str, original_filename: str
    ) -> str:
        """
        Process file from temporary file path

        Args:
            user_uuid: UUID of the user/chatbot
            file_path: Path to temporary file
            original_filename: Original filename

        Returns:
            str: Generated file ID
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")

        if not self.is_csv_or_excel(original_filename):
            raise ValueError("Only CSV and Excel files are supported")

        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        return await self.store_file(user_uuid, content, original_filename)

    async def fetch_files_for_user(
        self, chatbot_id: str, session_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve files for a chatbot, optionally scoped to a session.

        - If session_id is provided: return files matching both chatbot_id AND session_id.
        - If not: return files matching chatbot_id AND session_id IS NULL.
        """
        async with async_session() as session:
            # if session_id:
            # session-scoped files
            stmt = select(UserFile).filter(
                UserFile.chatbot_id == chatbot_id, UserFile.session_id == session_id
            )
            # else:
            #     # global/shared files (no session)
            #     stmt = (
            #         select(UserFile)
            #         .filter(
            #             UserFile.chatbot_id == chatbot_id,
            #             UserFile.session_id.is_(None)
            #         )
            #     )

            result = await session.execute(stmt)
            files = result.scalars().all()

        return [
            {
                "id": f.id,
                "filename": f.filename,
                "content": f.content,
                "uploaded_at": f.uploaded_at,
            }
            for f in files
        ]

    async def load_user_dataframes(
        self, chatbot_id: str, session_id: str
    ) -> List[pd.DataFrame]:
        """
        Fetch all CSV/Excel files for a user and load them into pandas DataFrames.

        Returns:
            List of DataFrames (in the same order as stored files).
        """
        raw_files = await self.fetch_files_for_user(chatbot_id, session_id)
        dfs: List[pd.DataFrame] = []

        for f in raw_files:
            name = f["filename"].lower()
            buffer = BytesIO(f["content"])

            if name.endswith(".csv"):
                dfs.append(pd.read_csv(buffer))
            elif name.endswith((".xls", ".xlsx")):
                dfs.append(pd.read_excel(buffer))
            # else: skip non-sheet files

        return dfs, raw_files
