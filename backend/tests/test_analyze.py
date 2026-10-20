"""The photo must reach the model as an image, never as a URL in the prompt text.

OpenAI and Vercel Blob are stubbed: no key, network or upload is needed.

    cd backend && pytest
"""

import base64
import sys
import types

import pytest

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def captured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-token-not-real")
    fake_blob = types.ModuleType("vercel_blob")
    fake_blob.put = lambda path, body, options=None: {"url": f"https://blob.example/{path}"}
    monkeypatch.setitem(sys.modules, "vercel_blob", fake_blob)
    sys.modules.pop("main", None)

    import openai

    calls = {}

    class Reply:
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content="stub reply"))]

    monkeypatch.setattr(openai.chat.completions, "create", lambda **kw: (calls.update(kw), Reply())[1])
    monkeypatch.setattr(openai.audio.transcriptions, "create", lambda **kw: "my cotton leaves are turning yellow")

    import main
    from fastapi.testclient import TestClient

    response = TestClient(main.app).post(
        "/analyze/",
        files={"image_file": ("leaf.png", PNG, "image/png"), "audio_file": ("q.mp3", b"ID3", "audio/mpeg")},
    )
    assert response.status_code == 200
    return calls


def test_photo_is_sent_as_an_image_part(captured):
    text, image = captured["messages"][0]["content"]
    assert text["type"] == "text"
    assert image["type"] == "image_url"
    url = image["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == PNG


def test_prompt_has_no_photo_url_and_no_false_model_claim(captured):
    text = captured["messages"][0]["content"][0]["text"]
    assert "blob.example" not in text
    assert "Gemini" not in text
    assert "my cotton leaves are turning yellow" in text


def test_prompt_forbids_doses_and_refers_to_kvk(captured):
    text = captured["messages"][0]["content"][0]["text"]
    assert "Do not give pesticide, fungicide or fertiliser doses" in text
    assert "Krishi Vigyan Kendra" in text
