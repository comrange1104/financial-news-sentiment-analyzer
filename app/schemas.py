"""Validated request and response contracts, also used by Swagger UI."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Label = Literal["positive", "negative", "neutral"]


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str | None = Field(default=None, max_length=1_000_000)
    url: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def validate_source(self):
        # Presence matters: {"text": "", "url": "..."} is also invalid.
        if len(self.model_fields_set & {"text", "url"}) != 1:
            raise ValueError("Provide exactly one field: text or url.")
        value = self.text if "text" in self.model_fields_set else self.url
        if value is None or not value.strip():
            raise ValueError("Input must be a non-empty string.")
        if self.text is not None:
            self.text = self.text.strip()
        if self.url is not None:
            self.url = self.url.strip()
        return self


class SentimentScores(BaseModel):
    positive: float = Field(ge=0, le=1)
    negative: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)


class PredictResponse(BaseModel):
    model: str
    label: Label
    confidence: float = Field(ge=0, le=1)
    scores: SentimentScores
    source_type: Literal["text", "url"]
    source_url: str | None
    token_count: int = Field(gt=0)
    chunk_count: int = Field(gt=0)
    aggregation: Literal["token_weighted_mean"] = "token_weighted_mean"
