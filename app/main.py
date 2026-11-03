"""Run with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.config import settings as default_settings
from app.errors import ServiceError
from app.schemas import PredictRequest, PredictResponse
from app.services.article_reader import ArticleReader
from app.services.sentiment import SentimentService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings = default_settings, *, sentiment=None, article_reader=None
) -> FastAPI:
    analyzer = sentiment if sentiment is not None else SentimentService(settings)
    reader = article_reader if article_reader is not None else ArticleReader(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            analyzer.load()
        except Exception:
            logger.exception(
                "Model failed to load. Health will report unavailable; restart after fixing the cause."
            )
        yield
        analyzer.unload()

    application = FastAPI(
        title="Financial News Sentiment Analyzer",
        description="Analyze English financial text or public article URLs with FinBERT on CPU.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.sentiment = analyzer
    application.state.article_reader = reader

    @application.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.get("/", tags=["System"])
    def introduction():
        return {
            "name": application.title,
            "description": "Financial news sentiment: positive, negative, or neutral, with all three scores.",
            "model": settings.model_id,
            "language": "English",
            "docs": "/docs",
            "predict": "/predict",
        }

    @application.get("/health", tags=["System"])
    def health():
        ready = analyzer.is_ready
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "unavailable",
                "model_ready": ready,
                "model": settings.model_id,
            },
        )

    @application.post(
        "/predict",
        response_model=PredictResponse,
        tags=["Sentiment"],
        responses={
            code: {"description": description}
            for code, description in {
                422: "Invalid input or token limit exceeded",
                502: "Article download/extraction failed",
                504: "Article download timed out",
                503: "Model unavailable",
                500: "Inference failed",
            }.items()
        },
    )
    def predict(
        payload: Annotated[
            PredictRequest,
            Body(
                openapi_examples={
                    "positive": {
                        "summary": "Positive financial news",
                        "value": {
                            "text": "The company reported record profits and raised its annual forecast."
                        },
                    },
                    "negative": {
                        "summary": "Negative financial news",
                        "value": {
                            "text": "The company reported a significant loss and warned of declining sales."
                        },
                    },
                    "neutral": {
                        "summary": "Neutral announcement",
                        "value": {
                            "text": "The company will publish its quarterly report on Tuesday."
                        },
                    },
                    "url": {
                        "summary": "NVIDIA earnings article",
                        "value": {
                            "url": "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025"
                        },
                    },
                }
            ),
        ],
    ):
        if not analyzer.is_ready:
            raise ServiceError(
                503, "Model is unavailable. Check server logs and restart the application."
            )
        try:
            source_url = None
            text = payload.text
            if payload.url is not None:
                article = reader.read(payload.url)
                text, source_url = article.text, article.url
            result = analyzer.predict(text)
            return PredictResponse(
                **result,
                source_type="url" if source_url is not None else "text",
                source_url=source_url,
            )
        except ServiceError:
            raise
        except Exception as exc:
            logger.exception("Prediction failed")
            raise ServiceError(500, "Unable to analyze this input. Please try again.") from exc

    return application


app = create_app()
