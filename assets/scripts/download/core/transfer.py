"""Atomic resumable HTTP transfers."""

from __future__ import annotations

from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)
import http.client
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone

from aminor_msa.utils.files import CHUNK_SIZE, sha256_file, write_json

from .models import Artifact
from .records import record_path, verify_artifact
from .validation import validate_artifact


def acquire(
    data_root: Path, artifact: Artifact, timeout: float = 30, retries: int = 3
) -> dict:
    """Acquire one request with integrity-checked resume and atomic publication.

    :param data_root: Output directory.
    :type data_root: Path
    :param artifact: Expected request.
    :type artifact: Artifact
    :param timeout: Socket timeout in seconds.
    :type timeout: float
    :param retries: Additional attempts for transient transport failures.
    :type retries: int
    :return: Provenance with complete or failed status.
    :rtype: dict
    """
    existing = verify_artifact(data_root, artifact)
    if existing["status"] == "verified":
        logger.debug("Verified existing artifact: %s", artifact.key)
        return {**existing, "status": "complete", "resumed": True}
    destination = data_root / artifact.relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries + 1):
        fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".part")
        try:
            # Transfer into a private partial file before validating its contents.
            request = urllib.request.Request(
                artifact.url,
                headers={
                    "User-Agent": "RNA-A-minors-acquisition/0.1",
                    "Accept-Encoding": "identity",
                },
            )
            with (
                os.fdopen(fd, "wb") as handle,
                urllib.request.urlopen(request, timeout=timeout) as response,
            ):
                if response.status != 200:
                    raise ValueError(f"Unexpected HTTP status: {response.status}")
                for chunk in iter(lambda: response.read(CHUNK_SIZE), b""):
                    handle.write(chunk)
                http_metadata = {
                    "http_status": response.status,
                    "final_url": response.url,
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                }
            diagnostics = validate_artifact(Path(temporary), artifact)
            record = {
                **asdict(artifact),
                **http_metadata,
                "status": "complete",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "bytes": Path(temporary).stat().st_size,
                "sha256": sha256_file(Path(temporary)),
                "validation": diagnostics,
            }
            # Publish verified bytes, then provenance; a crash is detected on resume.
            os.replace(temporary, destination)
            write_json(record_path(data_root, artifact), record)
            return record
        except (
            OSError,
            ValueError,
            EOFError,
            http.client.HTTPException,
        ) as error:
            retryable = isinstance(
                error, (OSError, http.client.HTTPException)
            ) and not isinstance(error, urllib.error.HTTPError)
            if isinstance(error, urllib.error.HTTPError):
                retryable = error.code in {408, 429, 500, 502, 503, 504}
                error.close()
            if retryable and attempt < retries:
                logger.warning("Retry %s for %s: %s", attempt + 1, artifact.key, error)
                time.sleep(min(2**attempt, 8))
                continue
            logger.error("Acquisition failed for %s", artifact.key, exc_info=True)
            record = {
                **asdict(artifact),
                "status": "failed",
                "error": str(error),
                "attempted_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(record_path(data_root, artifact), record)
            return record
        finally:
            Path(temporary).unlink(missing_ok=True)
    raise RuntimeError("Unreachable retry state")
