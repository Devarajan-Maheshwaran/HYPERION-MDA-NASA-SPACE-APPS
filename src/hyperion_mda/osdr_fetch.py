"""Download the NASA OSDR OSD-575 CMP file and verify it against the provenance manifest.

Usage:  python -m hyperion_mda.osdr_fetch [--cache-dir DIR]

This is the only module that uses the network. It sends no health data: it reads
the public OSDR file listing, downloads one public file, and checks the listed
name, size and restriction flag plus the file's size and SHA-256 against the
manifest. On any failure it reports the problem and leaves no unverified file in
the cache. Nothing is substituted.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from .osdr_source import (ChecksumMismatchError, OsdrSourceError, default_cache_dir,
                          load_manifest, verify_file)

USER_AGENT = "hyperion-mda-osdr-fetch"
TIMEOUT_S = 60


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=TIMEOUT_S)  # follows OSDR's redirect to storage


def check_listing(manifest: dict, listing_url: str | None = None) -> dict:
    """Confirm the official file listing still names this file, unrestricted, at this size."""
    url = listing_url or manifest["osdr_files_api"]
    with _open(url) as response:
        listing = json.load(response)
    entries = listing.get("studies", {}).get(manifest["study_id"], {}).get("study_files", [])
    entry = next((e for e in entries if e.get("file_name") == manifest["file_name"]), None)
    if entry is None:
        raise OsdrSourceError(f"{manifest['file_name']} is not in the OSDR file listing at {url}.")
    if entry.get("restricted") is not False:
        raise OsdrSourceError(f"OSDR lists {manifest['file_name']} as restricted; not downloading.")
    if entry.get("file_size") != manifest["file_size_bytes"]:
        raise ChecksumMismatchError(
            f"OSDR lists {manifest['file_name']} at {entry.get('file_size')} bytes, but the manifest "
            f"records {manifest['file_size_bytes']}. The source may have changed; not downloading.")
    return entry


def fetch(cache_dir: Path | None = None, *, listing_url: str | None = None,
          download_url: str | None = None) -> Path:
    """Download, verify, then move into the cache. Returns the verified path."""
    manifest = load_manifest()
    check_listing(manifest, listing_url)
    folder = cache_dir if cache_dir is not None else default_cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / manifest["file_name"]
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".part", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            with _open(download_url or manifest["download_url"]) as response:
                while chunk := response.read(65536):
                    tmp.write(chunk)
        except BaseException:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise
    try:
        verify_file(tmp_path, manifest)
    except OsdrSourceError:
        tmp_path.unlink(missing_ok=True)  # never leave an unverified file behind
        raise
    tmp_path.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="folder for the verified file (default: %(default)s → ~/.hyperion_mda/osdr/OSD-575)")
    args = parser.parse_args(argv)
    try:
        path = fetch(args.cache_dir)
    except (OsdrSourceError, OSError, ValueError) as exc:
        print(f"OSDR download FAILED: {exc}", file=sys.stderr)
        return 1
    manifest = load_manifest()
    print(f"Verified {manifest['file_name']} ({manifest['file_size_bytes']} bytes, "
          f"SHA-256 {manifest['sha256']}) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
