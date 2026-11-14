"""Provenance manifest and local verification for the NASA OSDR OSD-575 CMP file.

No network access happens here. The file is downloaded only by the explicit
``python -m hyperion_mda.osdr_fetch`` command. This module checks that a local
copy is byte-for-byte the file recorded in the provenance manifest. If the file is
missing or does not match, an error is raised; nothing is substituted.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

MANIFEST_RESOURCE = ("data", "osdr", "OSD-575.provenance.json")
CACHE_ENV_VAR = "HYPERION_MDA_DATA_DIR"


class OsdrSourceError(Exception):
    """The verified OSDR source file is not available for loading."""


class SourceFileMissingError(OsdrSourceError):
    """The OSDR file has not been downloaded to the local cache."""


class ChecksumMismatchError(OsdrSourceError):
    """The local file's size or SHA-256 differs from the provenance manifest."""


@dataclass(frozen=True)
class VerifiedFile:
    path: Path
    sha256: str
    size: int
    manifest: dict


def load_manifest() -> dict:
    """The provenance manifest shipped with the package (metadata only, no data)."""
    text = resources.files("hyperion_mda").joinpath(*MANIFEST_RESOURCE).read_text(encoding="utf-8")
    manifest = json.loads(text)
    for key in ("study_id", "file_name", "download_url", "file_size_bytes", "sha256", "retrieved_utc"):
        if not manifest.get(key):
            raise OsdrSourceError(f"Provenance manifest is missing '{key}'.")
    return manifest


def default_cache_dir() -> Path:
    """Local folder for downloaded OSDR files (override with HYPERION_MDA_DATA_DIR)."""
    base = os.environ.get(CACHE_ENV_VAR)
    root = Path(base) if base else Path.home() / ".hyperion_mda"
    return root / "osdr" / "OSD-575"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, manifest: dict) -> VerifiedFile:
    """Check size and SHA-256 against the manifest; raise instead of guessing."""
    if not path.is_file():
        raise SourceFileMissingError(
            f"{manifest['file_name']} was not found at {path}. Download it with: "
            "python -m hyperion_mda.osdr_fetch")
    size = path.stat().st_size
    digest = sha256_of(path)
    if size != manifest["file_size_bytes"] or digest != manifest["sha256"]:
        raise ChecksumMismatchError(
            f"{path.name} does not match the provenance manifest "
            f"(size {size} vs {manifest['file_size_bytes']}; SHA-256 {digest[:16]}… vs "
            f"{manifest['sha256'][:16]}…). The file was not loaded.")
    return VerifiedFile(path=path, sha256=digest, size=size, manifest=manifest)


def verified_cmp_file(cache_dir: Path | None = None) -> VerifiedFile:
    """Locate and verify the cached OSD-575 CMP file."""
    manifest = load_manifest()
    folder = cache_dir if cache_dir is not None else default_cache_dir()
    return verify_file(folder / manifest["file_name"], manifest)
