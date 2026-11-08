"""Where the photo classifier's backbone comes from.

The backbone is the public int8 ONNX export of DINOv2-small (Apache-2.0), pinned to one
revision and checked by sha256, so every copy is the same 24 MB file:

- locally and on hosts with a persistent disk: backend/models/, filled by scripts/get_model.py;
- on serverless hosts (Vercel), where nothing is fetched at build time: downloaded once per
  instance into a writable cache directory, and only when KISAN_FETCH_MODEL=1.

A download that doesn't match the checksum is deleted and never loaded. The download has a
connect and read timeout, so a stalled CDN fails the photo check instead of hanging the
function until the host kills it.
"""

import hashlib
import tempfile
from pathlib import Path

import httpx

from kisan import config

REVISION = "8b1f705a3a7f6f062f6bdd21986c1583d3ef105d"
URL = f"https://huggingface.co/onnx-community/dinov2-small/resolve/{REVISION}/onnx/model_quantized.onnx"
SHA256 = "c179f8f7f592449c4c1bca4cd124a7538021428c5ffb89afde9503935b197efb"
FILENAME = "dinov2_small_int8.onnx"
# 10 s to connect, 30 s between bytes: a 24 MB file from Hugging Face's CDN needs far less.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cache_dir() -> Path:
    return Path(config.load().kisan_model_cache or Path(tempfile.gettempdir()) / "kisan-models")


def fetch_allowed() -> bool:
    return config.load().kisan_fetch_model == "1"


def fetch(url: str, dest: Path, timeout: httpx.Timeout = TIMEOUT) -> None:
    """Stream url into dest, following the CDN redirect, with connect and read timeouts."""
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)


def download(dest: Path, url: str | None = None, expected: str | None = None) -> Path:
    """Download to dest atomically; refuse anything whose checksum doesn't match."""
    url, expected = url or URL, expected or SHA256
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        fetch(url, tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if sha256(tmp) != expected:
        tmp.unlink(missing_ok=True)
        raise ValueError("checksum mismatch: download refused")
    tmp.replace(dest)
    return dest


def backbone_path(model_dir: Path) -> Path | None:
    """The backbone file to load, or None if there is none and fetching isn't allowed."""
    bundled = model_dir / FILENAME
    if bundled.exists():
        return bundled
    cached = cache_dir() / FILENAME
    if cached.exists() and sha256(cached) == SHA256:
        return cached
    if not fetch_allowed():
        return None
    return download(cached)
