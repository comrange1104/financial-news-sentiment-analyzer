from types import SimpleNamespace

import pytest

from app.config import Settings
from app.errors import ServiceError
from app.services.sentiment import SentimentService, aggregate_scores, split_token_ids


@pytest.mark.parametrize("size", [1, 509, 510, 511, 1020, 1021, 20_000])
def test_chunks_cover_every_token_exactly_once(size):
    tokens = list(range(size))
    chunks = split_token_ids(tokens, 510)
    assert [token for chunk in chunks for token in chunk] == tokens
    assert all(0 < len(chunk) <= 510 for chunk in chunks)
    assert len(chunks) == (size + 509) // 510


def test_aggregation_weights_real_tokens_including_short_last_chunk():
    scores = aggregate_scores([[0.9, 0.05, 0.05], [0.1, 0.8, 0.1]], [510, 10])
    assert scores["positive"] == pytest.approx((0.9 * 510 + 0.1 * 10) / 520)
    assert sum(scores.values()) == pytest.approx(1)


@pytest.mark.parametrize(
    "rows,lengths",
    [([], []), ([[1, 0, 0]], [0]), ([[1, 0, 0]], [1, 2]), ([[float("nan"), 0, 1]], [1])],
)
def test_invalid_aggregation_is_rejected(rows, lengths):
    with pytest.raises(ValueError):
        aggregate_scores(rows, lengths)


class FakeTokenizer:
    def __init__(self, size):
        self.size = size
        self.seen = []

    def encode(self, text, **kwargs):
        return list(range(min(self.size, kwargs["max_length"])))

    def num_special_tokens_to_add(self, **kwargs):
        return 2

    def build_inputs_with_special_tokens(self, chunk):
        self.seen.extend(chunk)
        return [101, *chunk, 102]

    def pad(self, inputs, **kwargs):
        import torch

        rows = inputs["input_ids"]
        width = max(map(len, rows))
        return {"input_ids": torch.tensor([row + [0] * (width - len(row)) for row in rows])}


class FakeModel:
    # Intentionally different from FinBERT: code must honor id2label.
    config = SimpleNamespace(
        max_position_embeddings=512, id2label={0: "neutral", 1: "positive", 2: "negative"}
    )

    def __call__(self, input_ids):
        import torch

        assert input_ids.shape[1] <= 512
        return SimpleNamespace(logits=torch.tensor([[0.0, 4.0, -1.0]] * len(input_ids)))


def fake_service(size):
    service = SentimentService(Settings())
    service.tokenizer = FakeTokenizer(size)
    service.model = FakeModel()
    return service


def test_inference_preserves_tokens_and_reads_model_label_mapping():
    service = fake_service(510 * 5 + 7)  # Crosses both chunk and four-item batch boundaries.
    result = service.predict("Financial news")
    assert result["label"] == "positive"
    assert result["confidence"] == result["scores"]["positive"]
    assert result["chunk_count"] == 6
    assert service.tokenizer.seen == list(range(2557))
    assert result["token_count"] == 2557
    assert sum(result["scores"].values()) == pytest.approx(1)


def test_exact_token_limit_is_accepted():
    assert fake_service(20_000).predict("news")["token_count"] == 20_000


def test_excess_tokens_are_rejected_before_inference():
    service = fake_service(20_001)
    with pytest.raises(ServiceError) as error:
        service.predict("news")
    assert error.value.status_code == 422
    assert service.tokenizer.seen == []


@pytest.mark.parametrize("text", ["", "  \n\t "])
def test_empty_content_is_rejected(text):
    with pytest.raises(ServiceError) as error:
        fake_service(0).predict(text)
    assert error.value.status_code == 422


def test_unloaded_model_returns_503():
    with pytest.raises(ServiceError) as error:
        SentimentService(Settings()).predict("news")
    assert error.value.status_code == 503
