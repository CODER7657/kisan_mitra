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
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_DIR = Path(os.getenv("CROP_MODEL_DIR", Path(__file__).resolve().parent.parent / "models"))
BACKBONE_FILE = "dinov2_small_int8.onnx"
HEAD_FILE = "crop_head.json"
INPUT = {"size": 224, "resize_short_side": 256, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}


def readable(label: str) -> tuple[str, str]:
    """'Tomato___Late_blight' -> ('Tomato', 'Late blight')."""
    crop, _, condition = label.partition("___")
    crop = crop.replace("_(maize)", "").replace("_(including_sour)", "").replace(",_bell", " (bell)")
    condition = condition.replace("_", " ").strip()
    return crop.replace("_", " "), condition[:1].upper() + condition[1:]


def load_head(path: Path) -> dict:
    """Decode the head file: int8 weights with one float32 scale per class, and a float32 bias."""
    meta = json.loads(path.read_text(encoding="utf-8"))
    blob = meta["weights_base64"]
    if hashlib.sha256(blob.encode()).hexdigest() != meta["sha256"]:
        raise ValueError(f"{path} is corrupt: checksum mismatch")
    raw, k, d = base64.b64decode(blob), len(meta["classes"]), meta["dim"]
    q = np.frombuffer(raw[: k * d], dtype=np.int8).reshape(k, d).astype(np.float32)
    scale = np.frombuffer(raw[k * d: k * d + 4 * k], dtype=np.float32).reshape(k, 1)
    bias = np.frombuffer(raw[k * d + 4 * k:], dtype=np.float32)
    return {"W": q * scale, "b": bias, "classes": meta["classes"], "threshold": meta["threshold"]}


@lru_cache(maxsize=1)
def _load():
    import onnxruntime as ort

    session = ort.InferenceSession(str(MODEL_DIR / BACKBONE_FILE), providers=["CPUExecutionProvider"])
    return session, load_head(MODEL_DIR / HEAD_FILE)


def available() -> bool:
    return (MODEL_DIR / BACKBONE_FILE).exists() and (MODEL_DIR / HEAD_FILE).exists()


def preprocess(image: Image.Image, spec: dict = INPUT) -> np.ndarray:
    """Resize the short side, centre-crop and normalise, exactly as in the training notebook."""
    size, short = spec["size"], spec["resize_short_side"]
    image = image.convert("RGB")
    image.thumbnail((448, 448))  # training photos were stored at most 448 px wide; phone photos are larger
    w, h = image.size
    nw, nh = (short, int(short * h / w)) if w <= h else (int(short * w / h), short)
    image = image.resize((nw, nh), Image.BILINEAR)
    left, top = int(round((nw - size) / 2.0)), int(round((nh - size) / 2.0))
    image = image.crop((left, top, left + size, top + size))
    x = np.asarray(image, dtype=np.float32) / 255.0
    x = (x - np.array(spec["mean"], np.float32)) / np.array(spec["std"], np.float32)
    return x.transpose(2, 0, 1)[None]


def features(session, x: np.ndarray) -> np.ndarray:
    h = session.run(["last_hidden_state"], {session.get_inputs()[0].name: x})[0]
    return np.concatenate([h[:, 0], h[:, 1:].mean(1)], 1)


def probabilities(head: dict, f: np.ndarray) -> np.ndarray:
    z = f @ head["W"].T + head["b"]
    z -= z.max(axis=1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(axis=1, keepdims=True)


def classify(image_bytes: bytes, top_k: int = 3) -> dict | None:
    """Top guesses with probabilities, or None if the model isn't installed."""
    if not available():
        return None
    session, head = _load()
    x = preprocess(Image.open(io.BytesIO(image_bytes)))
    p = probabilities(head, features(session, x))[0]
    guesses = []
    for i in np.argsort(-p)[:top_k]:
        crop, condition = readable(head["classes"][i])
        guesses.append({"label": head["classes"][i], "crop": crop, "condition": condition,
                        "probability": round(float(p[i]), 3)})
    crops = sorted({readable(c)[0] for c in head["classes"]})
    return {"guesses": guesses, "confident": guesses[0]["probability"] >= head["threshold"],
            "threshold": head["threshold"], "crops_covered": crops}
