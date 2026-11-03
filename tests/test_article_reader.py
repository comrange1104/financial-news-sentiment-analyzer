import socket
from dataclasses import replace

import httpx
import pytest

from app.config import Settings
from app.errors import ServiceError
from app.services import article_reader as module
from app.services.article_reader import ArticleReader, validate_public_url

ARTICLE_HTML = b"""<!doctype html><html><head><title>Company profits rise</title></head><body>
<nav>Home Markets About</nav><article><h1>Company profits rise</h1>
<p>The company reported record profits for the financial year after revenue increased by twenty percent.
Management raised its forecast as demand for the company's products continued to expand across markets.</p>
<p>Operating costs remained stable and cash flow improved. The board announced a higher dividend,
while executives said they expected further growth in the following quarter.</p></article></body></html>"""


@pytest.fixture
def network(monkeypatch):
    def resolve(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(module.socket, "getaddrinfo", resolve)
    real_client = httpx.Client

    def install(handler):
        monkeypatch.setattr(
            module.httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
        )

    return install


@pytest.mark.parametrize(
    "url",
    [
        "ftp://news.example/a",
        "file:///etc/passwd",
        "not a URL",
        "http://localhost/a",
        "http://test.local/a",
        "http://service.internal/a",
        "https://user:pass@news.example/a",
        "https://news.example:8080/a",
        "https://news.example/\narticle",
        "http://news.example\\@127.0.0.1/",
    ],
)
def test_malformed_or_disallowed_url_is_rejected(url):
    with pytest.raises(ServiceError) as error:
        validate_public_url(url)
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "ff02::1",
    ],
)
def test_non_public_dns_targets_are_rejected(monkeypatch, address):
    monkeypatch.setattr(
        module.socket, "getaddrinfo", lambda *args, **kwargs: [(0, 0, 0, "", (address, 443))]
    )
    with pytest.raises(ServiceError) as error:
        validate_public_url("https://news.example/article")
    assert error.value.status_code == 422


def test_mixed_public_and_private_dns_answers_are_rejected(monkeypatch):
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (0, 0, 0, "", ("93.184.216.34", 443)),
            (0, 0, 0, "", ("10.0.0.1", 443)),
        ],
    )
    with pytest.raises(ServiceError):
        validate_public_url("https://news.example/article")


def test_dns_failure_returns_502(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror("Not found")

    monkeypatch.setattr(module.socket, "getaddrinfo", fail)
    with pytest.raises(ServiceError) as error:
        validate_public_url("https://missing.example/article")
    assert error.value.status_code == 502


def test_download_pins_ip_preserves_host_sni_and_extracts_article(network):
    def handler(request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "news.example"
        assert request.extensions["sni_hostname"] == "news.example"
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, content=ARTICLE_HTML
        )

    network(handler)
    result = ArticleReader(Settings()).read("https://news.example/article#section")
    assert "record profits" in result.text
    assert "Home Markets About" not in result.text
    assert result.url == "https://news.example/article"


def test_relative_redirect_resolves_again_and_returns_final_url(network):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "/new"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=ARTICLE_HTML)

    network(handler)
    result = ArticleReader(Settings()).read("https://news.example/old")
    assert result.url == "https://news.example/new"
    assert paths == ["/old", "/new"]


def test_redirect_to_localhost_is_blocked_before_second_connection(network):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://localhost/private"})

    network(handler)
    with pytest.raises(ServiceError) as error:
        ArticleReader(Settings()).read("https://news.example/old")
    assert error.value.status_code == 422
    assert len(calls) == 1


def test_redirect_loop_is_bounded(network):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "/loop"})

    network(handler)
    with pytest.raises(ServiceError) as error:
        ArticleReader(Settings()).read("https://news.example/loop")
    assert error.value.status_code == 502
    assert len(calls) == 4


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(403),
        httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF"),
        httpx.Response(
            200, headers={"content-type": "text/html"}, content=b"<html><body></body></html>"
        ),
    ],
)
def test_unusable_source_returns_502(network, response):
    network(lambda request: response)
    with pytest.raises(ServiceError) as error:
        ArticleReader(Settings()).read("https://news.example/article")
    assert error.value.status_code == 502


@pytest.mark.parametrize("advertise_size", [True, False])
def test_size_limit_applies_to_headers_and_streamed_bytes(network, advertise_size):
    headers = {"content-type": "text/html"}
    if advertise_size:
        headers["content-length"] = "10000"

    def handler(request):
        response = httpx.Response(200, headers=headers, content=ARTICLE_HTML)
        if not advertise_size:
            response.headers.pop("content-length", None)
        return response

    network(handler)
    with pytest.raises(ServiceError) as error:
        ArticleReader(replace(Settings(), max_html_bytes=32)).read("https://news.example/article")
    assert error.value.status_code == 502


def test_timeout_returns_504(network):
    def handler(request):
        raise httpx.ReadTimeout("Timed out", request=request)

    network(handler)
    with pytest.raises(ServiceError) as error:
        ArticleReader(Settings()).read("https://news.example/article")
    assert error.value.status_code == 504
