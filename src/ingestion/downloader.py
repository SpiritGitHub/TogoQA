"""Document downloader with SHA-256 versioning for TogoQA.

Downloads reference documents (RSCE, Annuaire national, etc.),
computes checksums, and maintains a versioning manifest.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "TogoQA-Bot/0.1 (+https://github.com/SpiritGitHub/TogoQA)"
DEFAULT_DOWNLOAD_DIR = "data/downloads"
MANIFEST_PATH = "data/downloads/manifest.json"


@dataclass
class DownloadEntry:
    url: str
    filename: str
    checksum: str
    size: int
    downloaded_at: str
    version: int = 1
    document_type: str = ""
    reference_period: str = ""
    source_id: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "filename": self.filename,
            "checksum": self.checksum,
            "size": self.size,
            "downloaded_at": self.downloaded_at,
            "version": self.version,
            "document_type": self.document_type,
            "reference_period": self.reference_period,
            "source_id": self.source_id,
        }


@dataclass
class DocumentDownloader:
    download_dir: str = DEFAULT_DOWNLOAD_DIR
    manifest_path: str = MANIFEST_PATH
    _manifest: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        os.makedirs(self.download_dir, exist_ok=True)
        self._load_manifest()

    def _load_manifest(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, encoding="utf-8") as f:
                self._manifest = json.load(f)
        else:
            self._manifest = {"documents": {}, "last_updated": ""}

    def _save_manifest(self):
        self._manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2, ensure_ascii=False)

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def is_duplicate(self, checksum: str) -> bool:
        for doc in self._manifest.get("documents", {}).values():
            if doc.get("checksum") == checksum:
                return True
        return False

    def get_version(self, filename: str) -> int:
        existing = self._manifest.get("documents", {}).get(filename)
        if existing:
            return existing.get("version", 0) + 1
        return 1

    async def download(
        self,
        url: str,
        filename: str | None = None,
        document_type: str = "",
        reference_period: str = "",
        source_id: str = "",
    ) -> DownloadEntry | None:
        """Download a document, compute SHA-256, update manifest."""
        if filename is None:
            filename = url.split("/")[-1].split("?")[0]

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=120.0,
            follow_redirects=True,
            verify=False,
        ) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Download failed for %s: %s", url, e)
                return None

        data = resp.content
        checksum = self.compute_checksum(data)

        if self.is_duplicate(checksum):
            logger.info("Duplicate detected (same checksum), skipping: %s", filename)
            return None

        version = self.get_version(filename)

        if version > 1:
            base, ext = os.path.splitext(filename)
            versioned_name = f"{base}_v{version}{ext}"
        else:
            versioned_name = filename

        filepath = os.path.join(self.download_dir, versioned_name)
        with open(filepath, "wb") as f:
            f.write(data)

        entry = DownloadEntry(
            url=url,
            filename=versioned_name,
            checksum=checksum,
            size=len(data),
            downloaded_at=datetime.now(timezone.utc).isoformat(),
            version=version,
            document_type=document_type,
            reference_period=reference_period,
            source_id=source_id,
        )

        self._manifest.setdefault("documents", {})[versioned_name] = entry.to_dict()
        self._save_manifest()

        logger.info("Downloaded %s (%d bytes, v%d, sha256=%s)", versioned_name, len(data), version, checksum[:12])
        return entry


# Known reference documents for manual or automated download
REFERENCE_DOCUMENTS = [
    {
        "name": "RSCE Togo 2025",
        "description": "Revue Sectorielle Conjointe de l'Education 2025",
        "document_type": "rapport",
        "reference_period": "2025",
        "source_id": "MEPS",
        "notes": "A telecharger manuellement depuis education.gouv.tg ou opendata.gouv.tg",
    },
    {
        "name": "Annuaire national des statistiques scolaires 2023-2024",
        "description": "Annuaire statistique du systeme educatif togolais",
        "document_type": "annuaire",
        "reference_period": "2023-2024",
        "source_id": "MEPS",
        "notes": "A telecharger manuellement depuis education.gouv.tg",
    },
]
