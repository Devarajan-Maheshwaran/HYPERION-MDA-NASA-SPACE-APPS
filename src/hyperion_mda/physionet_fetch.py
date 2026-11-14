"""Download PhysioNet "Wrist PPG During Exercise" v1.0.0 and verify every file.

Usage:  python -m hyperion_mda.physionet_fetch [--cache-dir DIR]

NON-ASTRONAUT methods-demonstration data (ODC-By 1.0; cite Jarchi & Casson 2017 and
PhysioNet). The data is never bundled or redistributed by this project. Flow:
1. download SHA256SUMS.txt and require it to match the hash pinned in the manifest
   (an upstream change is reported, not trusted);
2. download each listed file to a temporary name, check its SHA-256 against the
   pinned owner value, and only then move it into the cache.
Any failure is reported, unverified files are removed, and nothing is substituted.
Sends no data: plain HTTPS GET requests only.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

from .physionet_source import (PhysioNetChecksumError, PhysioNetSourceError, default_cache_dir,
                               load_manifest, sha256_of)

USER_AGENT = "hyperion-mda-physionet-fetch"
TIMEOUT_S = 120


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response, target.open("wb") as out:
        while chunk := response.read(1 << 16):
            out.write(chunk)


def fetch(cache_dir: Path | None = None, *, base_url: str | None = None, progress=print) -> Path:
    manifest = load_manifest()
    base = base_url or manifest["files_base_url"]
    folder = cache_dir if cache_dir is not None else default_cache_dir()
    folder.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        sums = Path(tmp) / "SHA256SUMS.txt"
        _download(base + "SHA256SUMS.txt", sums)
        if hashlib.sha256(sums.read_bytes()).hexdigest() != manifest["sha256sums_file_sha256"]:
            raise PhysioNetChecksumError(
                "PhysioNet's SHA256SUMS.txt differs from the pinned copy; the dataset may have changed. "
                "Nothing was downloaded.")
        for i, (name, expected) in enumerate(sorted(manifest["files"].items()), start=1):
            final = folder / name
            if final.is_file() and sha256_of(final) == expected:
                continue  # already verified
            part = Path(tmp) / name
            _download(base + name, part)
            actual = sha256_of(part)
            if actual != expected:
                raise PhysioNetChecksumError(f"{name}: SHA-256 {actual[:16]}… does not match {expected[:16]}…; "
                                             "download stopped and unverified files removed.")
            part.replace(final)
            if progress:
                progress(f"[{i}/{len(manifest['files'])}] verified {name}")
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        folder = fetch(args.cache_dir)
    except (PhysioNetSourceError, OSError, ValueError) as exc:
        print(f"PhysioNet download FAILED: {exc}", file=sys.stderr)
        return 1
    manifest = load_manifest()
    print(f"All {len(manifest['files'])} files verified against the owner-provided SHA-256 values -> {folder}")
    print("Licence: " + manifest["license"] + ". Cite: " + " | ".join(manifest["required_citations"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
