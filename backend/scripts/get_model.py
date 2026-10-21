"""Fetch the photo classifier's backbone: the public int8 ONNX export of DINOv2-small
(Apache-2.0), pinned to one revision and checked by sha256. About 24 MB.

    cd backend && python scripts/get_model.py

The head (models/crop_head.json) is small and lives in the repository.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

REVISION = "8b1f705a3a7f6f062f6bdd21986c1583d3ef105d"
URL = f"https://huggingface.co/onnx-community/dinov2-small/resolve/{REVISION}/onnx/model_quantized.onnx"
SHA256 = "c179f8f7f592449c4c1bca4cd124a7538021428c5ffb89afde9503935b197efb"
DEST = Path(__file__).resolve().parents[1] / "models" / "dinov2_small_int8.onnx"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if DEST.exists() and sha256(DEST) == SHA256:
        print(f"{DEST.name} already present")
        return
    DEST.parent.mkdir(exist_ok=True)
    tmp = DEST.with_suffix(".part")
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, tmp)
    if sha256(tmp) != SHA256:
        tmp.unlink()
        sys.exit("checksum mismatch: download refused")
    tmp.replace(DEST)
    print(f"saved {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
