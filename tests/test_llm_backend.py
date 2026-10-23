"""Exercise the HTTP adapter with in-memory sockets, never actual endpoints."""

import asyncio
import json
from unittest.mock import Mock

import pytest

from collusion.llm import backend as b
from collusion.llm.sampling import sampling_for


def request():
    return {"model_key": "qwen-9b", "endpoint": "https://offline.invalid/v1",
            "body": {"model": "llm", "messages": [], **sampling_for("qwen-9b"), "seed": 42}}


def connection(monkeypatch, status=200, payload=None):
    raw = {"choices": [{"message": {"content": '{"bid":4}', "reasoning_content": "private reasoning"}}],
           "usage": {"prompt_tokens": 5, "completion_tokens": 8, "prompt_tokens_details": {"cached_tokens": 3}}}
    response = Mock(status=status)
    response.read.return_value = (json.dumps(raw) if payload is None else payload).encode()
    conn = Mock()
    conn.getresponse.return_value = response
    factory = Mock(return_value=conn)
    monkeypatch.setattr(b.http.client, "HTTPSConnection", factory)
    return conn, factory


def test_http_body_auth_usage_and_reasoning(monkeypatch):
    conn, factory = connection(monkeypatch)
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid"}, token="dummy-test-proxy-token", timeout=5)
    result = asyncio.run(backend.complete(request()))
    assert backend.identity("qwen-9b") == "https://offline.invalid/v1"
    assert result.content == '{"bid":4}' and result.prompt_tokens == 5 and result.completion_tokens == 8
    assert result.raw["choices"][0]["message"]["reasoning_content"] == "private reasoning"
    args, kwargs = conn.request.call_args
    assert args == ("POST", "/v1/chat/completions")
    expected = dict(request()["body"])
    expected.update(expected.pop("extra_body"))
    assert json.loads(kwargs["body"]) == expected
    assert "extra_body" not in json.loads(kwargs["body"])
    assert result.cached_prompt_tokens == 3
    assert kwargs["headers"]["Authorization"] == "Bearer dummy-test-proxy-token"
    assert "dummy-test-proxy-token" not in json.dumps(request())
    factory.assert_called_once_with("offline.invalid", None, timeout=5)
    conn.close.assert_called_once()


@pytest.mark.parametrize("status,error", [(429, b.RetryableTransportError), (500, b.AmbiguousTransportError),
                                          (503, b.AmbiguousTransportError), (401, b.BackendError)])
def test_http_errors_are_classified_without_response_details(monkeypatch, status, error):
    conn, _ = connection(monkeypatch, status, "sensitive provider error details")
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid/v1"}, token="dummy")
    with pytest.raises(error) as caught:
        asyncio.run(backend.complete(request()))
    assert "sensitive" not in str(caught.value)
    conn.close.assert_called_once()


def test_connect_failure_is_retryable_but_lost_response_is_not(monkeypatch):
    conn, _ = connection(monkeypatch)
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid/v1"}, token="dummy")
    conn.connect.side_effect = OSError("offline")
    with pytest.raises(b.RetryableTransportError):
        asyncio.run(backend.complete(request()))
    conn.request.assert_not_called()
    conn.connect.side_effect = None
    conn.getresponse.side_effect = OSError("reply lost")
    with pytest.raises(b.AmbiguousTransportError):
        asyncio.run(backend.complete(request()))


def test_malformed_paid_response_is_retained(monkeypatch):
    connection(monkeypatch, payload="malformed data")
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid/v1"}, token="dummy")
    result = asyncio.run(backend.complete(request()))
    assert result.content == ""
    assert result.raw == {"malformed_response": "malformed data"}


@pytest.mark.parametrize("url", ["https://user:password@offline.invalid", "https://offline.invalid?token=dummy", "file:///tmp/a"])
def test_endpoint_credentials_forbidden(url):
    with pytest.raises(ValueError):
        b.endpoint_url(url)


def test_env_credentials_skip_secret_files(monkeypatch):
    monkeypatch.setenv("MODAL_PROXY_TOKEN_ID", "dummy-id")
    monkeypatch.setenv("MODAL_PROXY_TOKEN_SECRET", "dummy-secret")
    monkeypatch.setattr(b.Path, "is_file", Mock(side_effect=AssertionError("no files should be read")))
    assert b.modal_token() == "dummy-id.dummy-secret"


@pytest.mark.parametrize("status,payload,expected", [(200, '{"version":"0.31.test"}', "0.31.test"),
    (404, '{}', None), (200, 'invalid', None), (200, '[]', None)])
def test_version_endpoint_is_best_effort_and_authenticated(monkeypatch, status, payload, expected):
    conn, _ = connection(monkeypatch, status, payload)
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid/v1"}, token="dummy")
    assert asyncio.run(backend.server_version("qwen-9b")) == expected
    args, kwargs = conn.request.call_args
    assert args == ("GET", "/version")
    assert kwargs["headers"]["Authorization"] == "Bearer dummy"
    conn.close.assert_called_once()


def test_modal_no_upstream_503_is_safe_to_retry(monkeypatch):
    """Modal's proxy answers 503 "no upstreams available" before any container is ready: nothing was submitted."""
    connection(monkeypatch, 503, '{"error":"no upstreams available"}')
    backend = b.OpenAIBackend({"qwen-9b": "https://offline.invalid/v1"}, token="dummy")
    with pytest.raises(b.RetryableTransportError):
        asyncio.run(backend.complete(request()))
