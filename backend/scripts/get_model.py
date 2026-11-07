"""Fetch the photo classifier's backbone into backend/models/ (about 24 MB, checked by sha256).

    cd backend && python scripts/get_model.py

The head (models/crop_head.json) is small and lives in the repository. On Vercel the
backbone is fetched at runtime instead (see kisan/model_store.py).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kisan import model_store  # noqa: E402

DEST = ROOT / "models" / model_store.FILENAME


def main() -> None:
    if DEST.exists() and model_store.sha256(DEST) == model_store.SHA256:
        print(f"{DEST.name} already present")
        return
    print(f"downloading {model_store.URL}")
    try:
        model_store.download(DEST)
    except ValueError as e:
        sys.exit(str(e))
    print(f"saved {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
