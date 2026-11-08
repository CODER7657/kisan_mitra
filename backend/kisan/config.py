"""Settings read from the environment, checked when the app starts, and the model provider.

Groq is used when GROQ_API_KEY is set, OpenAI when only OPENAI_API_KEY is. Groq has
no vision model on this key, so with Groq the photo is read by the local classifier
only; with OpenAI the photo is also sent to GPT-4o.

Every variable keeps its old name and default. A value that cannot be used (a timeout of
0, retries of 50, a rate limit of "lots") stops the app at startup with a message naming
the variable, instead of failing on a farmer's first question. Keys and tokens are
SecretStr, so they never show up in a repr, a traceback or a log line.
"""

from dataclasses import dataclass, field
from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class ConfigError(RuntimeError):
    """The environment holds a value the app cannot run with."""


class Settings(BaseSettings):
    """Each field is read from the environment variable of the same name, in capitals."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Model provider
    groq_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    llm_provider: str = ""
    groq_chat_model: str = "qwen/qwen3.8-27b"
    groq_asr_model: str = "whisper-large-v3"
    openai_chat_model: str = "gpt-4o"
    # 25 s and one retry: a farmer is waiting on the page. Batch jobs raise both.
    kisan_llm_timeout: float = Field(25.0, gt=0, le=600)
    kisan_llm_retries: int = Field(1, ge=0, le=10)

    # Web
    allowed_origins: str | None = None
    rate_limit_per_min: int = Field(12, ge=1)

    # Uploads (off unless STORE_UPLOADS=1 and a token is set)
    store_uploads: str = ""
    blob_read_write_token: SecretStr | None = None

    # Photo classifier files
    crop_model_dir: str | None = None
    kisan_model_cache: str | None = None
    kisan_fetch_model: str = ""

    @property
    def uploads_enabled(self) -> bool:
        return self.store_uploads == "1" and bool(self.blob_token)

    @property
    def blob_token(self) -> str:
        return self.blob_read_write_token.get_secret_value() if self.blob_read_write_token else ""


def load() -> Settings:
    """Read the environment now. Raises ConfigError naming each bad variable (never its value)."""
    try:
        return Settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']).upper()}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"Invalid configuration: {problems}") from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The settings the app started with. Call get_settings.cache_clear() to re-read."""
    return load()


@dataclass(frozen=True)
class Provider:
    name: str  # "groq" or "openai"
    api_key: str = field(repr=False)
    base_url: str | None
    chat_model: str
    asr_model: str
    sees_images: bool


def provider() -> Provider | None:
    """Re-read per call (it is cheap), so a rotated key or a test's environment applies."""
    s = load()
    groq = s.groq_api_key.get_secret_value().strip()
    openai_key = s.openai_api_key.get_secret_value().strip()
    choice = s.llm_provider.strip().lower()
    if groq and choice != "openai":
        return Provider(
            "groq", groq, GROQ_BASE_URL, s.groq_chat_model, s.groq_asr_model, sees_images=False
        )
    if openai_key:
        return Provider(
            "openai", openai_key, None, s.openai_chat_model, "whisper-1", sees_images=True
        )
    return None


def client(p: Provider):
    """An API client that fails fast for a farmer waiting on the page: 25 s and one retry by
    default. Batch jobs (the safety eval) raise KISAN_LLM_TIMEOUT / KISAN_LLM_RETRIES to wait."""
    from openai import OpenAI

    s = load()
    return OpenAI(
        api_key=p.api_key,
        base_url=p.base_url,
        timeout=s.kisan_llm_timeout,
        max_retries=s.kisan_llm_retries,
    )
