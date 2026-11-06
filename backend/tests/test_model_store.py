"""The backbone is loaded only from a known file: bundled, cached and verified, or freshly
downloaded and verified. Nothing touches the network unless KISAN_FETCH_MODEL=1."""

import hashlib

import pytest

from kisan import model_store, vision

GOOD = b"pretend onnx bytes"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("KISAN_MODEL_CACHE", str(tmp_path / "cache"))
    monkeypatch.delenv("KISAN_FETCH_MODEL", raising=False)
    monkeypatch.setattr(model_store, "SHA256", GOOD_SHA)
    calls = []

    def fake_retrieve(url, dest):
        calls.append(url)
        with open(dest, "wb") as f:
            f.write(fake_retrieve.payload)

    fake_retrieve.payload = GOOD
    monkeypatch.setattr(model_store.urllib.request, "urlretrieve", fake_retrieve)
    return tmp_path, calls, fake_retrieve


def test_bundled_file_wins_and_nothing_is_downloaded(store, monkeypatch):
    tmp, calls, _ = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    (tmp / "models").mkdir()
    (tmp / "models" / model_store.FILENAME).write_bytes(GOOD)
    assert model_store.backbone_path(tmp / "models") == tmp / "models" / model_store.FILENAME
    assert calls == []


def test_no_file_and_no_permission_means_no_download(store):
    tmp, calls, _ = store
    assert model_store.backbone_path(tmp / "models") is None
    assert calls == []


def test_download_is_verified_then_cached(store, monkeypatch):
    tmp, calls, _ = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    path = model_store.backbone_path(tmp / "models")
    assert path == tmp / "cache" / model_store.FILENAME and path.read_bytes() == GOOD
    assert model_store.backbone_path(tmp / "models") == path  # second call uses the cache
    assert len(calls) == 1


def test_tampered_download_is_refused_and_deleted(store, monkeypatch):
    tmp, calls, fake = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    fake.payload = b"something else"
    with pytest.raises(ValueError, match="checksum mismatch"):
        model_store.backbone_path(tmp / "models")
    assert not any((tmp / "cache").glob("*"))


def test_corrupt_cache_is_replaced(store, monkeypatch):
    tmp, calls, _ = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    (tmp / "cache").mkdir()
    (tmp / "cache" / model_store.FILENAME).write_bytes(b"half a file")
    assert model_store.backbone_path(tmp / "models").read_bytes() == GOOD
    assert len(calls) == 1


def test_vision_is_available_when_it_may_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "MODEL_DIR", tmp_path)
    monkeypatch.setenv("KISAN_MODEL_CACHE", str(tmp_path / "cache"))
    monkeypatch.delenv("KISAN_FETCH_MODEL", raising=False)
    assert not vision.available()  # no head
    (tmp_path / vision.HEAD_FILE).write_text("{}")
    assert not vision.available()  # head but no backbone, fetching off
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    assert vision.available()
