"""The backbone is loaded only from a known file: bundled, cached and verified, or freshly
downloaded and verified. Nothing touches the network unless KISAN_FETCH_MODEL=1."""

import contextlib
import hashlib
import types

import httpx
import pytest

from kisan import model_store, vision

GOOD = b"pretend onnx bytes"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()


class FakeResponse(contextlib.AbstractContextManager):
    """What httpx.stream yields: a status check and the body in chunks."""

    def __init__(self, payload, error=None):
        self.payload, self.error = payload, error

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.error:
            raise self.error

    def iter_bytes(self, size):
        yield self.payload[:5]
        yield self.payload[5:]


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("KISAN_MODEL_CACHE", str(tmp_path / "cache"))
    monkeypatch.delenv("KISAN_FETCH_MODEL", raising=False)
    monkeypatch.setattr(model_store, "SHA256", GOOD_SHA)
    calls = []

    def fake_stream(method, url, **kw):
        calls.append(url)
        fake_retrieve.kwargs = kw
        return FakeResponse(fake_retrieve.payload)

    # The payload to serve, and the keyword arguments of the last download.
    fake_retrieve = types.SimpleNamespace(payload=GOOD, kwargs=None)
    monkeypatch.setattr(model_store.httpx, "stream", fake_stream)
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


def test_download_has_connect_and_read_timeouts_and_follows_the_cdn_redirect(store, monkeypatch):
    tmp, calls, fake = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    model_store.backbone_path(tmp / "models")
    timeout = fake.kwargs["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0 and timeout.read == 30.0
    assert fake.kwargs["follow_redirects"] is True


def test_failed_download_leaves_no_partial_file(store, monkeypatch):
    tmp, calls, _ = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")

    def stalled(method, url, **kw):
        raise httpx.ReadTimeout("no bytes for 30 s")

    monkeypatch.setattr(model_store.httpx, "stream", stalled)
    with pytest.raises(httpx.ReadTimeout):
        model_store.backbone_path(tmp / "models")
    assert not any((tmp / "cache").glob("*"))


def test_http_error_is_raised_not_cached(store, monkeypatch):
    tmp, calls, _ = store
    monkeypatch.setenv("KISAN_FETCH_MODEL", "1")
    error = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", "u"), response=httpx.Response(404)
    )
    monkeypatch.setattr(model_store.httpx, "stream", lambda m, u, **kw: FakeResponse(b"", error))
    with pytest.raises(httpx.HTTPStatusError):
        model_store.backbone_path(tmp / "models")
    assert not any((tmp / "cache").glob("*"))


def test_empty_cache_variable_falls_back_to_the_temp_dir(monkeypatch):
    monkeypatch.setenv("KISAN_MODEL_CACHE", "")
    assert model_store.cache_dir().name == "kisan-models"
