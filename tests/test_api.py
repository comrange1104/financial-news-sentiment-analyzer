import pytest
from fastapi.testclient import TestClient

from app.errors import ServiceError
from app.main import create_app
from app.services.article_reader import Article


class FakeSentiment:
    def __init__(self, *, fail_load=False, error=None):
        self.is_ready = False
        self.fail_load = fail_load
        self.error = error
        self.load_count = 0

    def load(self):
        self.load_count += 1
        if self.fail_load:
            raise RuntimeError("Model download failed")
        self.is_ready = True

    def unload(self):
        self.is_ready = False

    def predict(self, text):
        if self.error:
            raise self.error
        assert text.strip()
        return {
            "model": "ProsusAI/finbert",
            "label": "positive",
            "confidence": 0.8,
            "scores": {"positive": 0.8, "negative": 0.1, "neutral": 0.1},
            "token_count": 10,
            "chunk_count": 1,
            "aggregation": "token_weighted_mean",
        }


class FakeReader:
    def __init__(self, error=None):
        self.error = error

    def read(self, url):
        if self.error:
            raise self.error
        return Article("The company announced record profits.", "https://news.example/final")


@pytest.fixture
def client():
    with TestClient(create_app(sentiment=FakeSentiment(), article_reader=FakeReader())) as session:
        yield session


def test_introduction_health_and_openapi(client):
    assert client.get("/").json()["language"] == "English"
    assert client.get("/health").json()["model_ready"] is True
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/", "/health", "/predict"} <= paths.keys()


def test_text_prediction_schema(client):
    response = client.post("/predict", json={"text": "Profits increased."})
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "text"
    assert data["source_url"] is None
    assert data["confidence"] == data["scores"][data["label"]]
    assert sum(data["scores"].values()) == pytest.approx(1)


def test_url_prediction_reports_final_source(client):
    response = client.post("/predict", json={"url": "https://news.example/article"})
    assert response.status_code == 200
    assert response.json()["source_type"] == "url"
    assert response.json()["source_url"] == "https://news.example/final"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": None},
        {"text": 123},
        {"url": []},
        {"text": "a", "url": "https://news.example"},
        {"text": "", "url": "https://news.example"},
        {"text": None, "url": "https://news.example"},
        {"text": "news", "extra": True},
        {"text": "x" * 1_000_001},
    ],
)
def test_invalid_input_returns_json_422(client, payload):
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_invalid_json_returns_json_422(client):
    response = client.post("/predict", content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize("code", [422, 502, 504])
def test_article_errors_preserve_status_and_detail(code):
    with TestClient(
        create_app(
            sentiment=FakeSentiment(),
            article_reader=FakeReader(ServiceError(code, "Article error")),
        )
    ) as client:
        response = client.post("/predict", json={"url": "https://news.example/article"})
        assert response.status_code == code
        assert response.json() == {"detail": "Article error"}


def test_model_load_failure_keeps_health_available_and_predictions_503():
    analyzer = FakeSentiment(fail_load=True)
    with TestClient(create_app(sentiment=analyzer)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 503
        assert client.get("/health").json()["model_ready"] is False
        assert client.post("/predict", json={"text": "news"}).status_code == 503
    assert analyzer.load_count == 1


def test_model_is_loaded_once_and_unloaded_on_shutdown():
    analyzer = FakeSentiment()
    with TestClient(create_app(sentiment=analyzer)) as client:
        for _ in range(2):
            assert client.post("/predict", json={"text": "news"}).status_code == 200
        assert analyzer.load_count == 1
    assert analyzer.is_ready is False


def test_unexpected_inference_error_is_not_exposed():
    with TestClient(
        create_app(sentiment=FakeSentiment(error=RuntimeError("private details")))
    ) as client:
        response = client.post("/predict", json={"text": "news"})
        assert response.status_code == 500
        assert "private details" not in response.text
        assert "detail" in response.json()
