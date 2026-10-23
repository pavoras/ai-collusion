"""Async OpenAI-compatible HTTP and deterministic offline backends.

No credentials are read until a live backend is explicitly constructed.
Only connection failures before sending and explicit rate rejections are safe
to retry. A lost reply is ambiguous: the durable caller must stop, not resubmit.
"""

import asyncio
from dataclasses import dataclass, field
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
from urllib.parse import urlsplit

from .parsing import PAIRS
from .sampling import MODEL_CONFIG

MODEL_KEYS = tuple(MODEL_CONFIG)


class RetryableTransportError(Exception):
    """The request was definitely not submitted, or was explicitly rejected."""


class AmbiguousTransportError(Exception):
    """The endpoint may have completed the request; do not automatically retry."""


class BackendError(Exception):
    """A definitive non-retryable rejection (details deliberately redacted)."""


@dataclass
class Response:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict = field(default_factory=dict)
    cached_prompt_tokens: int | None = None


def modal_token(start=None):
    """Read only proxy credentials from env or parent files, without printing them."""
    names = ("MODAL_PROXY_TOKEN_ID", "MODAL_PROXY_TOKEN_SECRET")
    values = {name: os.environ.get(name) for name in names}
    folder = Path(start or Path.cwd()).resolve()
    for parent in (folder, *folder.parents):
        if all(values.values()):
            break
        for name in (".env", "tokens.env"):
            path = parent / name
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                key = key.strip()
                if separator and key in names and not values[key]:
                    values[key] = value.strip().strip("\"'")
    if not all(values.values()):
        raise ValueError("Modal proxy credentials are missing")
    return ".".join(values[name] for name in names)


def endpoint_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("endpoint must be an HTTP(S) URL without credentials, query or fragment")
    return url.rstrip("/") + ("" if parts.path.rstrip("/").endswith("/v1") else "/v1")


class OpenAIBackend:
    """One endpoint per model key; stdlib HTTP runs in worker threads."""

    def __init__(self, endpoints, *, token=None, timeout=1200):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.endpoints = {key: endpoint_url(value) for key, value in endpoints.items()}
        self._token = token if token is not None else modal_token()
        self.timeout = timeout

    def identity(self, model):
        return self.endpoints[model]

    async def complete(self, request):
        return await asyncio.to_thread(self._complete, request)

    async def server_version(self, model):
        """Best-effort authenticated GET /version after the warm-up, never logged with auth."""
        return await asyncio.to_thread(self._server_version, model)

    def _server_version(self, model):
        parts = urlsplit(self.endpoints[model])
        connection_type = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(parts.hostname, parts.port, timeout=min(self.timeout, 15))
        try:
            path = parts.path.removesuffix("/v1") + "/version"
            connection.request("GET", path, headers={"Authorization": f"Bearer {self._token}"})
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            if response.status == 200:
                version = json.loads(payload).get("version")
                if isinstance(version, str) and version:
                    return version
        except (OSError, http.client.HTTPException, ValueError, AttributeError):
            pass
        finally:
            connection.close()
        return None

    def _complete(self, request):
        parts = urlsplit(request["endpoint"])
        connection_type = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(parts.hostname, parts.port, timeout=self.timeout)
        try:
            try:
                connection.connect()
            except ssl.SSLCertVerificationError:
                raise BackendError("TLS certificate rejected") from None
            except OSError:
                raise RetryableTransportError("connection failed before submission") from None
            payload_body = dict(request["body"])
            payload_body.update(payload_body.pop("extra_body", {}))
            body = json.dumps(payload_body).encode("utf-8")
            try:
                connection.request("POST", parts.path + "/chat/completions", body=body,
                                   headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
                response = connection.getresponse()
                payload = response.read().decode("utf-8")
            except (OSError, http.client.HTTPException, UnicodeError):
                raise AmbiguousTransportError("reply lost after possible submission") from None
            if response.status == 429:
                raise RetryableTransportError("endpoint rate rejection")
            if response.status >= 500:
                raise AmbiguousTransportError("endpoint server error after possible submission")
            if response.status != 200:
                raise BackendError(f"endpoint rejected request (HTTP {response.status})")
            try:
                raw = json.loads(payload)
                message = raw["choices"][0]["message"]
                content = message.get("content") or ""
                usage = raw.get("usage") or {}
                if not isinstance(content, str):
                    raise TypeError
                details = usage.get("prompt_tokens_details") or {}
                return Response(content, usage.get("prompt_tokens"), usage.get("completion_tokens"), raw,
                                details.get("cached_tokens"))
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                # Preserve a received (possibly billed) malformed response for auditing.
                return Response("", raw={"malformed_response": payload})
        finally:
            connection.close()


class FakeBackend:
    """Seeded responses or a supplied response/error sequence; never uses credentials."""

    def __init__(self, responses=None, *, delay=0):
        self.responses = iter(responses) if responses is not None else None
        self.delay = delay
        self.calls = []
        self.active = 0
        self.peak_active = 0

    def identity(self, model):
        return "fake://v1/" + model

    async def server_version(self, model):
        return None

    async def complete(self, request):
        self.calls.append(request)
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.responses is not None:
                answer = next(self.responses)
                if isinstance(answer, Exception):
                    raise answer
                if isinstance(answer, Response):
                    return answer
            else:
                body = request["body"]
                context = body["messages"][-1]["content"]
                if '"A-B"' in context:
                    answer = json.dumps(dict.fromkeys(PAIRS, 0.1))
                elif '{"message":' in context:
                    cost = re.search(r"Your private cost: (\d+)", context).group(1)
                    answer = json.dumps({"message": f"My current cost is {cost}."})
                else:
                    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).digest()
                    answer = json.dumps({"bid": 2 + int.from_bytes(digest[:4]) % 6})
            return Response(answer, 100, 10, {"offline": True, "content": answer})
        finally:
            self.active -= 1
