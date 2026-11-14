"""Provenance manifest and local verification for PhysioNet "Wrist PPG During Exercise" v1.0.0.

NON-ASTRONAUT, terrestrial laboratory data, used only for a clearly labelled methods
demonstration. No network access here: files are downloaded only by
``python -m hyperion_mda.physionet_fetch``. Every file is checked against the
owner-provided SHA-256 values pinned in the manifest; nothing is substituted.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

MANIFEST_RESOURCE = ("data", "physionet", "wrist-1.0.0.provenance.json")
CACHE_ENV_VAR = "HYPERION_MDA_DATA_DIR"
PROVENANCE = "RECORDED-NON-ASTRONAUT"


class PhysioNetSourceError(Exception):
    """The verified PhysioNet files are not available for loading."""


class PhysioNetMissingError(PhysioNetSourceError):
    """Files have not been downloaded to the local cache."""


class PhysioNetChecksumError(PhysioNetSourceError):
    """A local file's SHA-256 differs from the owner-provided value in the manifest."""


@dataclass(frozen=True)
class VerifiedRecord:
    name: str
    header: Path
    signals: Path
    annotations: Path


def load_manifest() -> dict:
    text = resources.files("hyperion_mda").joinpath(*MANIFEST_RESOURCE).read_text(encoding="utf-8")
    manifest = json.loads(text)
    for key in ("dataset", "version", "license", "files", "records", "sha256sums_file_sha256", "files_base_url"):
        if not manifest.get(key):
            raise PhysioNetSourceError(f"PhysioNet manifest is missing '{key}'.")
    return manifest


def default_cache_dir() -> Path:
    base = os.environ.get(CACHE_ENV_VAR)
    root = Path(base) if base else Path.home() / ".hyperion_mda"
    return root / "physionet" / "wrist-1.0.0"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(folder: Path, name: str, manifest: dict) -> Path:
    expected = manifest["files"].get(name)
    if expected is None:
        raise PhysioNetSourceError(f"{name} is not listed in the pinned PhysioNet manifest.")
    path = folder / name
    if not path.is_file():
        raise PhysioNetMissingError(
            f"{name} was not found in {folder}. Download the dataset with: python -m hyperion_mda.physionet_fetch")
    actual = sha256_of(path)
    if actual != expected:
        raise PhysioNetChecksumError(
            f"{name} does not match the owner-provided SHA-256 ({actual[:16]}… vs {expected[:16]}…). Not loaded.")
    return path


def verified_record(name: str, cache_dir: Path | None = None) -> VerifiedRecord:
    """Verify the header, signal and annotation files of one record before any use."""
    manifest = load_manifest()
    if name not in manifest["records"]:
        raise PhysioNetSourceError(f"Unknown record {name!r}; expected one of {', '.join(manifest['records'])}.")
    folder = cache_dir if cache_dir is not None else default_cache_dir()
    return VerifiedRecord(name=name,
                          header=verify_file(folder, f"{name}.hea", manifest),
                          signals=verify_file(folder, f"{name}.dat", manifest),
                          annotations=verify_file(folder, f"{name}.atr", manifest))
