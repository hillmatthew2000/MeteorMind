"""Shared fixtures. Nothing in the test suite touches the network."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from requests.adapters import BaseAdapter

from meteormind.api import WeatherAPIHandler
from meteormind.cache import ResponseCache

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = "0123456789abcdef0123456789abcdef"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


Responder = Callable[[requests.PreparedRequest], tuple[int, Any]]


class FakeTransport(BaseAdapter):
    """A requests transport adapter that answers from registered routes.

    Routes are keyed by URL path; a route is either a ``(status, body)`` pair
    or a callable receiving the prepared request. Every request is recorded.
    """

    def __init__(self) -> None:
        super().__init__()
        self.routes: dict[str, tuple[int, Any] | Responder | Exception] = {}
        self.requests: list[requests.PreparedRequest] = []

    def add(self, path: str, response: tuple[int, Any] | Responder | Exception) -> None:
        self.routes[path] = response

    def calls(self, path: str) -> list[dict[str, list[str]]]:
        return [
            parse_qs(urlsplit(req.url or "").query)
            for req in self.requests
            if urlsplit(req.url or "").path == path
        ]

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        verify: bool | str = True,
        cert: bytes | str | tuple[bytes | str, bytes | str] | None = None,
        proxies: Mapping[str, str] | None = None,
    ) -> requests.Response:
        self.requests.append(request)
        path = urlsplit(request.url or "").path
        route = self.routes.get(path)
        if route is None:
            status, body = 404, {"cod": "404", "message": "not found"}
        elif isinstance(route, Exception):
            raise route
        elif callable(route):
            status, body = route(request)
        else:
            status, body = route
        response = requests.Response()
        response.status_code = status
        response.request = request
        response.url = request.url or ""
        response._content = body if isinstance(body, bytes) else json.dumps(body).encode()
        response.headers["Content-Type"] = "application/json"
        return response

    def close(self) -> None:
        pass


GEO_PATH = "/geo/1.0/direct"
WEATHER_PATH = "/data/2.5/weather"
FORECAST_PATH = "/data/2.5/forecast"


@pytest.fixture
def transport() -> FakeTransport:
    fake = FakeTransport()
    fake.add(GEO_PATH, (200, load_fixture("geocode_london.json")))
    fake.add(WEATHER_PATH, (200, load_fixture("weather_london.json")))
    fake.add(FORECAST_PATH, (200, load_fixture("forecast_london.json")))
    return fake


@pytest.fixture
def client(transport: FakeTransport) -> Iterator[WeatherAPIHandler]:
    session = requests.Session()
    session.mount("https://", transport)
    yield WeatherAPIHandler(API_KEY, session=session, cache=ResponseCache())
    session.close()


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app at a temporary home and hide any real API key."""
    home = tmp_path / "home"
    monkeypatch.setenv("METEORMIND_HOME", str(home))
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    return home
