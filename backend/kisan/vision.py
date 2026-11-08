"""Crop-photo classifier: a frozen DINOv2-small backbone and a small trained head, on CPU.

The backbone is the public int8 ONNX export of DINOv2-small (onnx-community/dinov2-small,
fetched by scripts/get_model.py). It turns a photo into 768 numbers (the CLS token and
the mean patch token). The head, trained in notebooks/crop_classifier_colab.ipynb on
PlantVillage plus PlantDoc's field photos, maps them to 38 crop/condition classes
across 14 crops. A photo of any other crop still gets a guess, with low confidence,
which is why answers below the threshold are reported as "not sure".
"""

import base64
import hashlib
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from kisan import config, model_store

if TYPE_CHECKING:
    from onnxruntime import InferenceSession

Floats = NDArray[np.float32]


class InputSpec(TypedDict):
    size: int
    resize_short_side: int
    mean: list[float]
    std: list[float]


class Head(TypedDict):
    W: Floats
    b: Floats
    classes: list[str]
    threshold: float


class Guess(TypedDict):
    label: str
    crop: str
    condition: str
    probability: float


class Photo(TypedDict):
    guesses: list[Guess]
    confident: bool
    threshold: float
    crops_covered: list[str]


#: Override for tests; None means CROP_MODEL_DIR, else backend/models. Resolved when used, not at
#: import, so importing the classifier does not validate (and fail on) unrelated settings, and
#: a CROP_MODEL_DIR loaded from .env after import still applies.
MODEL_DIR: Path | None = None
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


def model_dir() -> Path:
    if MODEL_DIR is not None:
        return MODEL_DIR
    return Path(config.load().crop_model_dir or DEFAULT_MODEL_DIR)


BACKBONE_FILE = model_store.FILENAME
HEAD_FILE = "crop_head.json"
INPUT: InputSpec = {
    "size": 224,
    "resize_short_side": 256,
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
}
# A small file can decode to a huge image: a 0.45 MB PNG of 12000x12000 took 1.3 GB, past a
# free host's 512 MB. Normal phone photos (12 MP) are well under this.
MAX_PIXELS = 30_000_000


def readable(label: str) -> tuple[str, str]:
    """'Tomato___Late_blight' -> ('Tomato', 'Late blight')."""
    crop, _, condition = label.partition("___")
    crop = (
        crop.replace("_(maize)", "").replace("_(including_sour)", "").replace(",_bell", " (bell)")
    )
    condition = condition.replace("_", " ").strip()
    return crop.replace("_", " "), condition[:1].upper() + condition[1:]


def load_head(path: Path) -> Head:
    """Decode the head file: int8 weights with one float32 scale per class, and a float32 bias."""
    meta = json.loads(path.read_text(encoding="utf-8"))
    blob = meta["weights_base64"]
    if hashlib.sha256(blob.encode()).hexdigest() != meta["sha256"]:
        raise ValueError(f"{path} is corrupt: checksum mismatch")
    raw, k, d = base64.b64decode(blob), len(meta["classes"]), meta["dim"]
    q = np.frombuffer(raw[: k * d], dtype=np.int8).reshape(k, d).astype(np.float32)
    scale = np.frombuffer(raw[k * d : k * d + 4 * k], dtype=np.float32).reshape(k, 1)
    bias = np.frombuffer(raw[k * d + 4 * k :], dtype=np.float32)
    return {"W": q * scale, "b": bias, "classes": meta["classes"], "threshold": meta["threshold"]}


@lru_cache(maxsize=1)
def _load() -> tuple["InferenceSession", Head]:
    import onnxruntime as ort

    path = model_store.backbone_path(model_dir())
    if path is None:
        raise FileNotFoundError("photo classifier backbone is not available")
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return session, load_head(model_dir() / HEAD_FILE)


def available() -> bool:
    """True when a photo can be classified: the head is here, and the backbone is or may be fetched."""
    if not (model_dir() / HEAD_FILE).exists():
        return False
    return (
        (model_dir() / BACKBONE_FILE).exists()
        or model_store.fetch_allowed()
        or (model_store.cache_dir() / BACKBONE_FILE).exists()
    )


def open_photo(image_bytes: bytes) -> Image.Image:
    """Read the header and refuse images too big to decode. A JPEG above about 4000x3600
    (a 48 MP phone photo, say) is decoded at half or quarter scale; smaller ones, including
    normal 12 MP photos, are decoded in full exactly as before."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.format == "JPEG":
        image.draft("RGB", (1792, 1792))
    w, h = image.size
    if w * h > MAX_PIXELS:
        raise ValueError(f"photo is {w}x{h}, over {MAX_PIXELS} pixels")
    return image


def preprocess(image: Image.Image, spec: InputSpec = INPUT) -> Floats:
    """Resize the short side, centre-crop and normalise, exactly as in the training notebook."""
    size, short = spec["size"], spec["resize_short_side"]
    image = image.convert("RGB")
    image.thumbnail(
        (448, 448)
    )  # training photos were stored at most 448 px wide; phone photos are larger
    w, h = image.size
    nw, nh = (short, int(short * h / w)) if w <= h else (int(short * w / h), short)
    image = image.resize((nw, nh), Image.Resampling.BILINEAR)
    left, top = int(round((nw - size) / 2.0)), int(round((nh - size) / 2.0))
    image = image.crop((left, top, left + size, top + size))
    x = np.asarray(image, dtype=np.float32) / 255.0
    # Explicit dtype: numpy's stubs widen this expression's type (float32 stays float32).
    x = np.asarray(
        (x - np.array(spec["mean"], np.float32)) / np.array(spec["std"], np.float32),
        dtype=np.float32,
    )
    return x.transpose(2, 0, 1)[None]


def features(session: "InferenceSession", x: Floats) -> Floats:
    # onnxruntime is untyped; the backbone outputs float32 (batch, tokens, 384).
    h: Floats = session.run(["last_hidden_state"], {session.get_inputs()[0].name: x})[0]
    return np.concatenate([h[:, 0], h[:, 1:].mean(1)], 1)


def probabilities(head: Head, f: Floats) -> Floats:
    z = f @ head["W"].T + head["b"]
    z -= z.max(axis=1, keepdims=True)
    p: Floats = np.exp(z)  # numpy 2.1 types ufunc results as Any
    total: Floats = p.sum(axis=1, keepdims=True)  # and keepdims sums too
    return p / total


def classify(image_bytes: bytes, top_k: int = 3) -> Photo | None:
    """Top guesses with probabilities, or None if the model isn't installed."""
    if not available():
        return None
    x = preprocess(open_photo(image_bytes))
    session, head = _load()
    p = probabilities(head, features(session, x))[0]
    guesses: list[Guess] = []
    for i in np.argsort(-p)[:top_k]:
        crop, condition = readable(head["classes"][i])
        guesses.append(
            {
                "label": head["classes"][i],
                "crop": crop,
                "condition": condition,
                "probability": round(float(p[i]), 3),
            }
        )
    crops = sorted({readable(c)[0] for c in head["classes"]})
    return {
        "guesses": guesses,
        "confident": guesses[0]["probability"] >= head["threshold"],
        "threshold": head["threshold"],
        "crops_covered": crops,
    }
