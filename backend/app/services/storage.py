import os
import time
import logging
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # Allow falling back to standard env vars if settings aren't populated properly
        supabase_url = os.environ.get("SUPABASE_URL", getattr(settings, "SUPABASE_URL", ""))
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", getattr(settings, "SUPABASE_SERVICE_KEY", ""))
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not fully configured. Storage features may fail.")
            
        # Create client only if we have credentials, or create a dummy one for testing
        if supabase_url and supabase_key:
            self.client: Client = create_client(supabase_url, supabase_key)
        else:
            self.client = None
            
        self.bucket_name = "invoice-documents"

    def upload_file(self, file_content: bytes, storage_path: str, content_type: str) -> None:
        """
        Uploads a file to Supabase storage.
        Raises an exception if the upload fails.
        """
        if not self.client:
            raise RuntimeError("Supabase client not configured")
            
        try:
            start_time = time.time()
            res = self.client.storage.from_(self.bucket_name).upload(
                file=file_content,
                path=storage_path,
                file_options={"content-type": content_type}
            )
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info("storage_upload_completed", extra={"storage_path": storage_path, "duration_ms": duration})
        except Exception as e:
            logger.exception("Failed to upload to Supabase", extra={"storage_path": storage_path})
            raise RuntimeError("Storage upload failed") from e

    def download_file(self, storage_path: str) -> bytes:
        """
        Downloads a file from Supabase storage and returns its bytes.
        """
        if not self.client:
            raise RuntimeError("Supabase client not configured")
            
        try:
            start_time = time.time()
            data = self.client.storage.from_(self.bucket_name).download(storage_path)
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info("storage_download_completed", extra={"storage_path": storage_path, "duration_ms": duration})
            return data
        except Exception as e:
            logger.exception("Failed to download from Supabase", extra={"storage_path": storage_path})
            raise RuntimeError("Storage download failed") from e

    def delete_file(self, storage_path: str) -> None:
        """
        Deletes a file from Supabase storage.
        """
        if not self.client:
            return
            
        try:
            start_time = time.time()
            self.client.storage.from_(self.bucket_name).remove([storage_path])
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info("storage_delete_completed", extra={"storage_path": storage_path, "duration_ms": duration})
        except Exception:
            logger.exception("Failed to delete from Supabase", extra={"storage_path": storage_path})
            # Not raising here to avoid breaking cleanup routines
            
storage_service = StorageService()
