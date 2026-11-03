"""FinBERT inference with complete, non-overlapping token coverage."""

import logging
import math
import os
from threading import Lock

from app.config import Settings
from app.errors import ServiceError

logger = logging.getLogger(__name__)
LABELS = ("positive", "negative", "neutral")


def split_token_ids(token_ids: list[int], chunk_size: int) -> list[list[int]]:
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive.")
    return [token_ids[i : i + chunk_size] for i in range(0, len(token_ids), chunk_size)]


def aggregate_scores(probabilities: list[list[float]], lengths: list[int]) -> dict[str, float]:
    """Average each class probability, weighted by real content token counts."""
    if not lengths or len(probabilities) != len(lengths) or any(n <= 0 for n in lengths):
        raise ValueError("Probabilities and positive chunk lengths must match.")
    if any(
        len(row) != 3 or any(not math.isfinite(x) or x < 0 for x in row) for row in probabilities
    ):
        raise ValueError("Expected three finite, non-negative scores per chunk.")
    total = sum(lengths)
    weighted = [
        sum(row[i] * n for row, n in zip(probabilities, lengths, strict=True)) / total
        for i in range(3)
    ]
    normalizer = sum(weighted)
    if normalizer <= 0:
        raise ValueError("Scores must have a positive sum.")
    return {label: score / normalizer for label, score in zip(LABELS, weighted, strict=True)}


class SentimentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tokenizer = None
        self.model = None
        self._lock = Lock()

    @property
    def is_ready(self) -> bool:
        return self.tokenizer is not None and self.model is not None

    def load(self) -> None:
        # Lazy imports keep API validation tests independent of model downloads.
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(min(4, os.cpu_count() or 1))
        tokenizer = AutoTokenizer.from_pretrained(
            self.settings.model_id, revision=self.settings.model_revision
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.settings.model_id, revision=self.settings.model_revision, use_safetensors=True
        )
        labels = {str(label).lower() for label in model.config.id2label.values()}
        if labels != set(LABELS):
            raise RuntimeError("The model must expose positive, negative and neutral labels.")
        model.to("cpu")
        model.eval()
        self.tokenizer, self.model = tokenizer, model
        logger.info("Loaded %s on CPU", self.settings.model_id)

    def unload(self) -> None:
        self.model = None
        self.tokenizer = None

    def predict(self, text: str) -> dict:
        if not self.is_ready:
            raise ServiceError(
                503, "Model is unavailable. Check server logs and restart the application."
            )
        text = " ".join(text.split())
        if not text:
            raise ServiceError(422, "No text to analyze.")
        if len(text) > self.settings.max_input_characters:
            raise ServiceError(422, "Text is too large. Please shorten the input.")

        import torch

        # Serialize CPU work and bound memory when multiple requests arrive.
        with self._lock:
            token_ids = self.tokenizer.encode(
                text,
                add_special_tokens=False,
                truncation=True,
                max_length=self.settings.max_content_tokens + 1,
            )
            if len(token_ids) > self.settings.max_content_tokens:
                raise ServiceError(
                    422,
                    f"Text exceeds {self.settings.max_content_tokens:,} content tokens. Please shorten it.",
                )
            if not token_ids:
                raise ServiceError(422, "Input contains no analyzable tokens.")
            special = self.tokenizer.num_special_tokens_to_add(pair=False)
            context = min(
                self.settings.model_context_tokens, self.model.config.max_position_embeddings
            )
            chunks = split_token_ids(token_ids, context - special)
            # Do not assume classifier ID ordering: read it from model config.
            model_labels = [str(self.model.config.id2label[i]).lower() for i in range(3)]
            order = [model_labels.index(label) for label in LABELS]
            probabilities = []
            with torch.inference_mode():
                for start in range(0, len(chunks), self.settings.inference_batch_size):
                    batch = chunks[start : start + self.settings.inference_batch_size]
                    input_ids = [
                        self.tokenizer.build_inputs_with_special_tokens(chunk) for chunk in batch
                    ]
                    inputs = self.tokenizer.pad(
                        {"input_ids": input_ids}, padding=True, return_tensors="pt"
                    )
                    output = self.model(**inputs).logits.softmax(dim=-1).cpu().tolist()
                    probabilities.extend([[row[i] for i in order] for row in output])
            scores = aggregate_scores(probabilities, [len(chunk) for chunk in chunks])
        label = max(scores, key=scores.get)
        return {
            "model": self.settings.model_id,
            "label": label,
            "confidence": scores[label],
            "scores": scores,
            "token_count": len(token_ids),
            "chunk_count": len(chunks),
            "aggregation": "token_weighted_mean",
        }
