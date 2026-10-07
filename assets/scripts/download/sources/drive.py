"""Sources drive."""

from __future__ import annotations

import csv
import importlib
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from aminor_msa.utils.files import sha256_file
from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.config import ROOT
from assets.scripts.download.core.models import Artifact
from assets.scripts.download.core.records import verify_artifact

from .supplied import SUPPLIED, import_source

logger = get_custom_logger(__name__)


SOURCE_FOLDER = (
    "https://drive.google.com/drive/folders/1ZFsVgR5ueOf8TyxznjYAWOPkJFGbAkzK"
)


TASK_DOCUMENT = "https://docs.google.com/document/d/1ldhO9f8A3VH1H6uC1TY05Ez32zh7_08NauZ7ZgYYHHg/edit"


def route_material(relative_name: str, data_root: Path, reference_root: Path) -> Path:
    """Route supplied materials, rejecting unsafe folder member paths.

    :param relative_name: Relative filename reported by Drive.
    :type relative_name: str
    :param data_root: Dataset directory.
    :type data_root: Path
    :param reference_root: Directory for supplied documents.
    :type reference_root: Path
    :return: Destination path.
    :rtype: Path
    :raises ValueError: If the source path is unsafe.
    """
    relative = PurePosixPath(relative_name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in relative_name
        or not relative.name
    ):
        raise ValueError("Unsafe Drive member path")
    for filename, artifact in SUPPLIED:
        if relative.name == filename:
            return data_root / artifact.relative_path
    if relative.suffix.lower() in {".pdf", ".docx"}:
        return reference_root / relative.name
    return reference_root.parent / "materials" / Path(relative_name)


def _gdown():
    try:
        return importlib.import_module("gdown")
    except ModuleNotFoundError as error:
        logger.error("Google Drive support is unavailable", exc_info=True)
        raise RuntimeError("Install the project environment with: uv sync") from error


def download_materials(
    data_root: Path,
    reference_root: Path,
    folder_url: str | None = None,
    source_dir: Path | None = None,
    timeout: float = 30,
    cookies_file: Path | None = None,
    refresh_sources: bool = False,
) -> dict[str, int]:
    """Fetch original materials and write a readable source manifest.

    Without a folder URL, use the task document and its three supplied file links.
    Existing verified files are reused. Conflicting supplied snapshots are not
    overwritten. Folder discovery does not download complete files.

    :param data_root: Dataset directory, including acquisition configuration.
    :type data_root: Path
    :param reference_root: PDF and task-document directory.
    :type reference_root: Path
    :param folder_url: Optional shared folder URL; restricted folders need cookies.
    :type folder_url: str | None
    :param source_dir: Optional local folder containing original inputs.
    :type source_dir: Path | None
    :param timeout: Network timeout in seconds.
    :type timeout: float
    :param cookies_file: Optional Netscape cookies file for restricted Drive sources.
    :type cookies_file: Path | None
    :param refresh_sources: Rediscover the shared folder instead of using its manifest.
    :type refresh_sources: bool
    :return: Counts of downloaded, imported and reused files.
    :rtype: dict[str, int]
    :raises ValueError: On unsafe paths, ambiguous routing or invalid files.
    :raises RuntimeError: If Drive support is missing or a transfer fails.
    """
    manifest = data_root / "config/sources.csv"
    previous = {}
    if manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as handle:
            previous = {row["url"]: row for row in csv.DictReader(handle)}
    sources = [(filename, artifact.url) for filename, artifact in SUPPLIED]
    sources.append(("AminorsMSA_Main.docx", TASK_DOCUMENT))
    if source_dir is not None:
        folder_url = None
    if folder_url == SOURCE_FOLDER and previous and not refresh_sources:
        sources = [(row["source_file"], row["url"]) for row in previous.values()]
    elif folder_url:
        if (
            urlparse(folder_url).hostname != "drive.google.com"
            or "/folders/" not in folder_url
        ):
            raise ValueError("Expected a Google Drive folder URL")
        # List the shared folder first, then download only files needing restoration.
        entries = _gdown().download_folder(
            url=folder_url,
            skip_download=True,
            quiet=True,
            use_cookies=cookies_file is not None,
            cookies_file=None if cookies_file is None else str(cookies_file),
            timeout=timeout,
        )
        if not entries:
            raise ValueError("The shared folder contains no downloadable files")
        sources = [
            (entry.path, "https://drive.google.com/file/d/" + entry.id + "/view")
            for entry in entries
        ]
        names = {PurePosixPath(name).name for name, _ in sources}
        sources.extend(
            (filename, artifact.url)
            for filename, artifact in SUPPLIED
            if filename not in names
        )

    destinations = [
        route_material(name, data_root, reference_root) for name, _ in sources
    ]
    if len(set(destinations)) != len(destinations):
        raise ValueError("Multiple Drive files resolve to the same destination")
    counts = dict.fromkeys(("downloaded", "imported", "reused"), 0)
    rows = {
        url: {
            "source_file": name,
            "url": url,
            "destination": os.path.relpath(destination, ROOT),
            "sha256": previous.get(url, {}).get("sha256", ""),
        }
        for (name, url), destination in zip(sources, destinations)
    }
    for (name, url), destination in zip(sources, destinations):
        filename = PurePosixPath(name).name
        supplied = next((a for f, a in SUPPLIED if f == filename), None)
        artifact = (
            None
            if supplied is None
            else Artifact(
                supplied.key,
                supplied.kind,
                supplied.accession,
                url,
                supplied.relative_path,
            )
        )
        known = previous.get(url, {})
        reusable = False
        if artifact is not None:
            reusable = verify_artifact(data_root, artifact)["status"] == "verified"
        elif destination.is_file() and known.get("sha256"):
            reusable = sha256_file(destination) == known["sha256"]
        # Google Docs exports can change while keeping the same URL. Always
        # refresh this source so the local reference follows the shared doc.
        is_task_document = url == TASK_DOCUMENT
        if is_task_document:
            reusable = False
        if reusable:
            counts["reused"] += 1
            logger.info("Already present: %s", destination)
        elif (
            artifact is not None
            and destination.is_file()
            and verify_artifact(data_root, artifact)["status"] == "unrecorded"
            and known.get("sha256") == sha256_file(destination)
        ):
            # Restore ignored provenance from a pinned, hash-matching source snapshot.
            import_source(destination, data_root, artifact)
            counts["imported"] += 1
        elif source_dir is not None and artifact is not None:
            import_source(source_dir / filename, data_root, artifact)
            counts["imported"] += 1
        elif (
            source_dir is not None
            and artifact is None
            and (source_dir / filename).is_file()
        ):
            candidate = source_dir / filename
            if (
                not is_task_document
                and destination.exists()
                and sha256_file(destination) != sha256_file(candidate)
            ):
                raise ValueError("Existing material differs from the local source")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, destination)
            counts["imported"] += 1
        elif (
            artifact is not None
            and destination.is_file()
            and not folder_url
            and verify_artifact(data_root, artifact)["status"] == "unrecorded"
        ):
            # REMARK: Canonical original files may be included in a checkout
            # without their ignored provenance records. Register those copies.
            if known.get("sha256") and sha256_file(destination) != known["sha256"]:
                raise ValueError("Canonical input differs from the source manifest")
            import_source(destination, data_root, artifact)
            counts["imported"] += 1
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                dir=destination.parent, prefix=".download-"
            ) as temporary:
                candidate = Path(temporary) / filename
                file_id = re.search(r"/(?:file|document)/d/([^/]+)", url)
                if file_id is None:
                    raise ValueError("Invalid supplied Drive file URL")
                logger.info("Downloading %s from %s", name, url)
                _gdown().download(
                    id=file_id[1],
                    output=str(candidate),
                    quiet=False,
                    use_cookies=cookies_file is not None,
                    cookies_file=None if cookies_file is None else str(cookies_file),
                    timeout=timeout,
                    retries=2,
                    format="docx" if destination.suffix.lower() == ".docx" else None,
                )
                if not candidate.is_file() or candidate.stat().st_size == 0:
                    raise RuntimeError("Drive did not return a nonempty file")
                if artifact is not None:
                    import_source(candidate, data_root, artifact)
                else:
                    if destination.suffix.lower() == ".docx":
                        with zipfile.ZipFile(candidate) as document:
                            if "word/document.xml" not in document.namelist():
                                raise ValueError("Drive did not return a Word document")
                    if (
                        not is_task_document
                        and destination.exists()
                        and sha256_file(destination) != sha256_file(candidate)
                    ):
                        raise ValueError(
                            "Existing material differs from the supplied source"
                        )
                    os.replace(candidate, destination)
                counts["downloaded"] += 1
        rows[url] = {
            "source_file": name,
            "url": url,
            "destination": os.path.relpath(destination, ROOT),
            "sha256": sha256_file(destination),
        }
        # Persist completed source rows after each file, including partial runs.
        manifest.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(dir=manifest.parent, suffix=".part")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["source_file", "url", "destination", "sha256"]
                )
                writer.writeheader()
                writer.writerows(rows.values())
            os.replace(temporary_name, manifest)
        finally:
            Path(temporary_name).unlink(missing_ok=True)
    logger.info(
        "Materials: downloaded=%s, imported=%s, reused=%s",
        counts["downloaded"],
        counts["imported"],
        counts["reused"],
    )
    return counts
