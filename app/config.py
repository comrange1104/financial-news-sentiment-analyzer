"""Small, explicit defaults for a local CPU application."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_id: str = "ProsusAI/finbert"
    model_revision: str = "0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031"
    max_content_tokens: int = 20_000
    model_context_tokens: int = 512
    inference_batch_size: int = 4
    download_timeout_seconds: float = 15.0
    max_html_bytes: int = 5 * 1024 * 1024
    max_redirects: int = 3
    max_input_characters: int = 1_000_000


settings = Settings()
