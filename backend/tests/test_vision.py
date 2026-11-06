import io

import numpy as np
import pytest
from PIL import Image

from kisan import vision

SPEC = {"size": 224, "resize_short_side": 256, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}


def test_labels_read_like_words():
    assert vision.readable("Tomato___Late_blight") == ("Tomato", "Late blight")
    assert vision.readable("Corn_(maize)___Common_rust_") == ("Corn", "Common rust")
    assert vision.readable("Pepper,_bell___healthy") == ("Pepper (bell)", "Healthy")


@pytest.mark.parametrize("size", [(640, 480), (300, 900), (256, 256)])
def test_preprocess_matches_training(size):
    x = vision.preprocess(Image.new("RGB", size, (255, 0, 0)), SPEC)
    assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32
    assert np.allclose(x[0, 0], (1 - 0.485) / 0.229, atol=1e-5)
    assert np.allclose(x[0, 1], (0 - 0.456) / 0.224, atol=1e-5)


def test_no_model_means_no_guess(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "MODEL_DIR", tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64)).save(buf, "PNG")
    assert vision.classify(buf.getvalue()) is None


def test_head_file_round_trips(tmp_path):
    import base64, hashlib, json

    rng = np.random.default_rng(0)
    q = rng.integers(-127, 128, (3, 4), dtype=np.int8)
    s = np.array([0.01, 0.02, 0.03], np.float32)
    b = np.array([0.1, -0.2, 0.3], np.float32)
    blob = base64.b64encode(q.tobytes() + s.tobytes() + b.tobytes()).decode()
    path = tmp_path / "head.json"
    path.write_text(json.dumps({"classes": ["a", "b", "c"], "dim": 4, "threshold": 0.5, "weights_base64": blob,
                                "sha256": hashlib.sha256(blob.encode()).hexdigest()}))
    head = vision.load_head(path)
    assert np.allclose(head["W"], q * s[:, None]) and np.allclose(head["b"], b)
    path.write_text(path.read_text().replace(blob[:8], "AAAAAAAA"))
    with pytest.raises(ValueError):
        vision.load_head(path)


@pytest.mark.skipif(not vision.available(), reason="model not downloaded (scripts/get_model.py)")
def test_installed_model_returns_a_ranked_guess():
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (40, 120, 40)).save(buf, "JPEG")
    r = vision.classify(buf.getvalue())
    probs = [g["probability"] for g in r["guesses"]]
    assert len(probs) == 3 and probs == sorted(probs, reverse=True) and 0 < sum(probs) <= 1.001
    assert len(r["crops_covered"]) == 14


def encoded(size, fmt):
    buf = io.BytesIO()
    Image.new("RGB", size, (40, 120, 40)).save(buf, fmt)
    return buf.getvalue()


def test_oversized_photo_is_refused_before_decoding(monkeypatch):
    monkeypatch.setattr(vision, "MAX_PIXELS", 100 * 100)
    with pytest.raises(ValueError, match="over 10000 pixels"):
        vision.open_photo(encoded((101, 100), "PNG"))
    assert vision.open_photo(encoded((100, 100), "PNG")).size == (100, 100)


def test_phone_sized_jpeg_is_decoded_in_full():
    assert vision.open_photo(encoded((4000, 3000), "JPEG")).size == (4000, 3000)


def test_very_large_jpeg_is_decoded_at_reduced_scale():
    # 48 MP would pass MAX_PIXELS only because the JPEG decoder scales it down first
    image = vision.open_photo(encoded((8000, 6000), "JPEG"))
    assert image.size == (4000, 3000)
    assert vision.preprocess(image).shape == (1, 3, 224, 224)


def test_not_an_image_is_an_error():
    with pytest.raises(Exception):
        vision.open_photo(b"definitely not a photo")
