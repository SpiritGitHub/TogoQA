"""MinIO storage module for TogoQA raw documents.

Uploads HTML/PDF/CSV to MinIO with SHA-256 dedup,
updates raw_storage_path in the documents table.
"""

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "togoqa")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "togoqa_minio_dev")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "togoqa-documents")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

CONTENT_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".json": "application/json",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def get_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return CONTENT_TYPES.get(ext, "application/octet-stream")


def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class StorageResult:
    object_name: str
    bucket: str
    checksum: str
    size: int
    content_type: str
    uploaded_at: str
    is_duplicate: bool = False


class MinIOStorage:
    """Manages raw document storage in MinIO."""

    def __init__(
        self,
        endpoint: str = MINIO_ENDPOINT,
        access_key: str = MINIO_ACCESS_KEY,
        secret_key: str = MINIO_SECRET_KEY,
        bucket: str = MINIO_BUCKET,
        secure: bool = MINIO_SECURE,
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.secure = secure
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from minio import Minio
                self._client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                )
            except ImportError:
                raise ImportError("pip install minio")
        return self._client

    def ensure_bucket(self):
        client = self._get_client()
        if not client.bucket_exists(self.bucket):
            client.make_bucket(self.bucket)
            logger.info("Created bucket: %s", self.bucket)

    def object_exists(self, object_name: str) -> bool:
        client = self._get_client()
        try:
            client.stat_object(self.bucket, object_name)
            return True
        except Exception:
            return False

    def find_by_checksum(self, checksum: str, prefix: str = "") -> str | None:
        """Search for an object with matching checksum in metadata."""
        client = self._get_client()
        for obj in client.list_objects(self.bucket, prefix=prefix):
            try:
                stat = client.stat_object(self.bucket, obj.object_name)
                if stat.metadata and stat.metadata.get("x-amz-meta-sha256") == checksum:
                    return obj.object_name
            except Exception:
                continue
        return None

    def upload(
        self,
        data: bytes,
        object_name: str,
        source_url: str = "",
        check_duplicate: bool = True,
    ) -> StorageResult:
        """Upload raw document to MinIO with SHA-256 and dedup check."""
        checksum = compute_checksum(data)
        content_type = get_content_type(object_name)

        if check_duplicate:
            prefix = object_name.rsplit("/", 1)[0] + "/" if "/" in object_name else ""
            existing = self.find_by_checksum(checksum, prefix)
            if existing:
                logger.info("Duplicate found: %s (same as %s)", object_name, existing)
                return StorageResult(
                    object_name=existing,
                    bucket=self.bucket,
                    checksum=checksum,
                    size=len(data),
                    content_type=content_type,
                    uploaded_at=datetime.now(timezone.utc).isoformat(),
                    is_duplicate=True,
                )

        client = self._get_client()
        self.ensure_bucket()

        metadata = {
            "sha256": checksum,
            "source-url": source_url[:512] if source_url else "",
            "uploaded-at": datetime.now(timezone.utc).isoformat(),
        }

        client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata=metadata,
        )

        logger.info("Uploaded %s (%d bytes, sha256=%s)", object_name, len(data), checksum[:12])

        return StorageResult(
            object_name=object_name,
            bucket=self.bucket,
            checksum=checksum,
            size=len(data),
            content_type=content_type,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )

    def upload_file(self, filepath: str, object_name: str | None = None, source_url: str = "") -> StorageResult:
        """Upload a local file to MinIO."""
        if object_name is None:
            object_name = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            data = f.read()

        return self.upload(data, object_name, source_url=source_url)

    def download(self, object_name: str) -> bytes:
        client = self._get_client()
        response = client.get_object(self.bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def build_object_name(self, source_id: str, filename: str, year: str = "") -> str:
        """Build a structured object path: source_id/year/filename."""
        parts = [source_id.lower()]
        if year:
            parts.append(year)
        parts.append(filename)
        return "/".join(parts)
