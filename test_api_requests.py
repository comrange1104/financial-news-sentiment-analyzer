"""End-to-end checks against a running server. No pytest/model mocks are used here."""

import argparse
import json
import math

import requests


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_prediction(data, source_type):
    require(data["model"] == "ProsusAI/finbert", "Unexpected model")
    scores = data["scores"]
    require(set(scores) == {"positive", "negative", "neutral"}, "Missing scores")
    require(all(math.isfinite(s) and 0 <= s <= 1 for s in scores.values()), "Invalid scores")
    require(math.isclose(sum(scores.values()), 1, abs_tol=1e-5), "Scores do not sum to one")
    require(data["label"] == max(scores, key=scores.get), "Label differs from highest score")
    require(math.isclose(data["confidence"], scores[data["label"]]), "Confidence mismatch")
    require(data["source_type"] == source_type, "Source type mismatch")
    require(data["token_count"] > 0 and data["chunk_count"] > 0, "Missing coverage metadata")
    require(data["aggregation"] == "token_weighted_mean", "Unexpected aggregation")
    require((data["source_url"] is not None) == (source_type == "url"), "Source URL mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--url", action="append", default=[], help="Public article URL; repeat for multiple sources"
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    with requests.Session() as session:
        for path in ["/", "/health", "/docs"]:
            response = session.get(base + path, timeout=20)
            require(
                response.status_code == 200, f"{path}: {response.status_code} {response.text[:500]}"
            )
        samples = [
            "The company reported record profits and raised its annual forecast.",
            "The company reported a significant loss and warned of declining sales.",
            "The company will publish its quarterly report on Tuesday.",
            "Revenue increased and operating profit improved. " * 150,
        ]
        for index, text in enumerate(samples):
            response = session.post(base + "/predict", json={"text": text}, timeout=300)
            require(response.status_code == 200, f"Prediction failed: {response.text}")
            data = response.json()
            validate_prediction(data, "text")
            if index < 3:
                expected_label = ["positive", "negative", "neutral"][index]
                require(
                    data["label"] == expected_label,
                    f"Sample {index + 1}: expected {expected_label}",
                )
            if index == 3:
                require(data["chunk_count"] > 1, "Long text was not split")
            print(json.dumps({"sample": index + 1, **data}, ensure_ascii=False))
        invalid_inputs = [
            {},
            {"text": " "},
            {"text": 123},
            {"text": "a", "url": "https://example.com"},
            {"url": "file:///etc/passwd"},
            {"url": "http://127.0.0.1"},
            {"text": "profit " * 20_001},
        ]
        for payload in invalid_inputs:
            response = session.post(base + "/predict", json=payload, timeout=60)
            require(response.status_code == 422, f"Invalid input returned {response.status_code}")
            require("detail" in response.json(), "Error response has no detail")
        for url in args.url:
            response = session.post(base + "/predict", json={"url": url}, timeout=300)
            require(response.status_code == 200, f"URL failed ({url}): {response.text}")
            validate_prediction(response.json(), "url")
            print(json.dumps(response.json(), ensure_ascii=False))
    print(
        f"PASS: system endpoints, 4 text predictions, 7 invalid inputs, {len(args.url)} article URLs"
    )


if __name__ == "__main__":
    main()
