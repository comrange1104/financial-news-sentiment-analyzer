"""Extract public HTML articles without connecting to unvalidated DNS targets."""

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from app.config import Settings
from app.errors import ServiceError


@dataclass(frozen=True)
class Article:
    text: str
    url: str


def validate_public_url(url: str) -> tuple[httpx.URL, list[str]]:
    """Resolve once; return public IPs that the downloader will connect to directly."""
    try:
        parts = urlsplit(url)
        if any(ord(char) < 32 or ord(char) == 127 for char in url) or "\\" in url:
            raise ValueError("Control characters and backslashes are forbidden.")
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("Only absolute HTTP/HTTPS URLs are supported.")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Credentials in URLs are forbidden.")
        target = httpx.URL(url).copy_with(fragment=None)
        host = target.host.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Local hosts are forbidden.")
        port = target.port or (443 if target.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError("Only public web ports 80 and 443 are supported.")
    except (ValueError, httpx.InvalidURL) as exc:
        raise ServiceError(
            422, "Invalid or disallowed URL. Use a public HTTP/HTTPS article URL."
        ) from exc

    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ServiceError(502, "Cannot resolve the article website.") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses:
        raise ServiceError(502, "Cannot resolve the article website.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
            # IPv4-mapped IPv6 must obey the embedded IPv4 address policy too.
            embedded = getattr(ip, "ipv4_mapped", None)
            if (
                not ip.is_global
                or ip.is_multicast
                or ip.is_reserved
                or (embedded is not None and (not embedded.is_global or embedded.is_multicast))
            ):
                raise ValueError("Non-public destination.")
        except ValueError as exc:
            raise ServiceError(422, "URL must resolve exclusively to public IP addresses.") from exc
    return target, addresses


class ArticleReader:
    def __init__(self, settings: Settings):
        self.settings = settings

    def read(self, url: str) -> Article:
        html, final_url = self._download(url)
        try:
            text = trafilatura.extract(
                html,
                url=final_url,
                include_comments=False,
                include_tables=False,
                include_links=False,
                favor_precision=True,
                output_format="txt",
            )
        except Exception as exc:
            raise ServiceError(
                502, "Could not extract article text. Please paste the text instead."
            ) from exc
        text = " ".join((text or "").split())
        if len(text) < 80:
            raise ServiceError(
                502,
                "No readable article found. The page may require JavaScript, a subscription, or block access. Paste the text instead.",
            )
        if len(text) > self.settings.max_input_characters:
            raise ServiceError(422, "Extracted article is too large. Please paste a shorter text.")
        return Article(text=text, url=final_url)

    def _download(self, url: str) -> tuple[bytes, str]:
        deadline = time.monotonic() + self.settings.download_timeout_seconds
        for redirect_count in range(self.settings.max_redirects + 1):
            target, addresses = validate_public_url(url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ServiceError(504, "Timed out while downloading the article.")
            # Pin the TCP destination to a validated address (no second DNS lookup).
            # Host + SNI retain the original website and normal certificate checks.
            connect_url = target.copy_with(host=addresses[0])
            headers = {
                "Host": target.netloc.decode("ascii"),
                "User-Agent": "FinancialNewsSentimentAnalyzer/1.0 (educational local API)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Encoding": "identity",
            }
            try:
                # A fresh pool per hop prevents sharing TLS sessions across hostnames.
                with httpx.Client(
                    timeout=remaining, follow_redirects=False, trust_env=False
                ) as client:
                    with client.stream(
                        "GET",
                        connect_url,
                        headers=headers,
                        extensions={"sni_hostname": target.host},
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location or redirect_count == self.settings.max_redirects:
                                raise ServiceError(
                                    502, "Article has a missing or excessive redirect."
                                )
                            url = urljoin(str(target), location)
                            continue
                        if response.status_code != 200:
                            raise ServiceError(
                                502,
                                f"Article website returned HTTP {response.status_code}. Paste the text instead.",
                            )
                        content_type = (
                            response.headers.get("content-type", "")
                            .split(";", 1)[0]
                            .strip()
                            .lower()
                        )
                        if content_type not in {"text/html", "application/xhtml+xml"}:
                            raise ServiceError(502, "URL did not return an HTML page.")
                        length = response.headers.get("content-length", "")
                        if length.isdigit() and int(length) > self.settings.max_html_bytes:
                            raise ServiceError(502, "HTML page exceeds the 5 MB download limit.")
                        body = bytearray()
                        for chunk in response.iter_bytes(chunk_size=64 * 1024):
                            if time.monotonic() > deadline:
                                raise ServiceError(504, "Timed out while downloading the article.")
                            if len(body) + len(chunk) > self.settings.max_html_bytes:
                                raise ServiceError(
                                    502, "HTML page exceeds the 5 MB download limit."
                                )
                            body.extend(chunk)
                        return bytes(body), str(target)
            except httpx.TimeoutException as exc:
                raise ServiceError(504, "Timed out while downloading the article.") from exc
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                raise ServiceError(
                    502, "Cannot download this article. Paste the text instead."
                ) from exc
        raise ServiceError(502, "Too many redirects.")
