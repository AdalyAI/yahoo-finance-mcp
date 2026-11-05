"""The served app accepts a Descope M2M token or the static key on /mcp and keeps /health open."""

import time

import jwt
import pytest
from adaly_m2m_auth import CallerAuthenticator, KeyStore, TokenVerifier
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

import server

PROJECT_ID = "P2testproject"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
}
_MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


_KEYS = KeyStore.preloaded({"k1": _KEY.public_key()})


def _token(roles=("mcp:call", "env:prod")):
    now = int(time.time())
    return jwt.encode({"sub": "K2", "iss": PROJECT_ID, "exp": now + 600, "roles": list(roles)}, _KEY, algorithm="RS256", headers={"kid": "k1"})


_AUTH = CallerAuthenticator(TokenVerifier(PROJECT_ID, allowed_envs=("staging", "prod"), key_store=_KEYS), "static")
# The MCP session manager starts once per process, so every test shares one app and swaps its authenticator.
_APP = server.build_app(_AUTH)


@pytest.fixture(scope="module")
def shared_client():
    with TestClient(_APP) as client:
        yield client


@pytest.fixture
def client(shared_client):
    _APP.authenticator = _AUTH
    yield shared_client
    _APP.authenticator = _AUTH


def test_token_reaches_mcp(client):
    response = client.post("/mcp", json=_INIT, headers={**_MCP_HEADERS, "Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200


def test_static_key_reaches_mcp(client):
    response = client.post("/mcp", json=_INIT, headers={**_MCP_HEADERS, "x-api-key": "static"})
    assert response.status_code == 200


def test_token_without_role_and_no_key_refused(client):
    response = client.post(
        "/mcp", json=_INIT, headers={**_MCP_HEADERS, "Authorization": f"Bearer {_token(['env:prod'])}"}
    )
    assert response.status_code == 403


def test_health_open_without_credentials(client):
    assert client.get("/health").status_code == 200


def test_unconfigured_fails_closed(client):
    _APP.authenticator = CallerAuthenticator(None, "")
    assert client.post("/mcp", json=_INIT, headers=_MCP_HEADERS).status_code == 503
    assert client.get("/health").status_code == 200


def test_production_wiring_reads_api_key_and_project(monkeypatch):
    monkeypatch.setenv("API_KEY", "static")
    monkeypatch.setenv("DESCOPE_M2M_PROJECT_ID", PROJECT_ID)
    app = server.build_app()
    assert app.authenticator.static_key == "static"
    assert app.authenticator.static_header == "x-api-key"
    assert app.authenticator.verifier is not None
    assert app.authenticator.verifier.allowed_envs == frozenset({"staging", "prod"})
    assert app.exempt_paths == frozenset({"/health"})
