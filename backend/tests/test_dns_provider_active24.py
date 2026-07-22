import base64
import hashlib
import hmac
from unittest.mock import Mock

import pytest
import requests

from services.acme.dns_providers.active24 import Active24DnsProvider


class Response:
    def __init__(self, status=200, data=None, content=True):
        self.status_code = status
        self._data = data
        self.content = b"x" if content else b""

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


@pytest.fixture
def provider():
    return Active24DnsProvider({"api_key": "identifier", "api_secret": "super-secret"})


def test_schema_and_required_credentials():
    schema = Active24DnsProvider.get_credential_schema()
    assert [(x["label"], x["type"]) for x in schema[:2]] == [("Identifier", "text"), ("Secret key", "password")]
    with pytest.raises(ValueError):
        Active24DnsProvider({"api_secret": "x"})
    with pytest.raises(ValueError):
        Active24DnsProvider({"api_key": "x"})


def test_signing_uses_utc_and_path_without_query(provider):
    timestamp = 1784720000
    assert provider._canonical_string("GET", "/v2/check?ignored=true", timestamp) == "GET /v2/check 1784720000"
    headers = provider._headers("POST", "/v2/service/7/dns/record?x=1", timestamp)
    canonical = "POST /v2/service/7/dns/record 1784720000"
    signature = hmac.new(b"super-secret", canonical.encode(), hashlib.sha1).hexdigest()
    assert base64.b64decode(headers["Authorization"].split()[1]).decode() == f"identifier:{signature}"
    assert headers["Date"].endswith("Z")


def test_longest_suffix_and_substring_protection(provider, monkeypatch):
    calls = []
    def request(method, path, payload=None):
        calls.append(path)
        if path == "/v1/user/self/service":
            return True, {"services": [{"domain": "example.cz"}, {"domain": "sub.example.cz"}]}, ""
        if path == "/v1/user/self/zone/sub.example.cz":
            return True, {"serviceId": 9}, ""
        return False, None, "unexpected"
    monkeypatch.setattr(provider, "_request", request)
    assert provider.get_zone_for_domain("host.sub.example.cz") == "sub.example.cz"
    assert provider.get_zone_for_domain("notexample.cz") is None


def test_create_and_exact_cleanup(provider, monkeypatch):
    records = [
        {"id": 1, "type": "TXT", "name": "_acme-challenge", "content": "token-A"},
        {"id": 2, "type": "TXT", "name": "_acme-challenge", "content": "token-B"},
        {"id": 3, "type": "TXT", "name": "_acme-challenge", "content": "permanent"},
    ]
    deleted = []
    def request(method, path, payload=None):
        if path == "/v1/user/self/service":
            return True, {"services": [{"domain": "example.cz"}]}, ""
        if path == "/v1/user/self/zone/example.cz":
            return True, {"serviceId": 7}, ""
        if path == "/v2/service/7/dns/record" and method == "GET":
            return True, records, ""
        if method == "DELETE":
            deleted.append(path.rsplit("/", 1)[1])
            return True, None, ""
        return True, {}, ""
    monkeypatch.setattr(provider, "_request", request)
    assert provider.delete_txt_record_exact("example.cz", "_acme-challenge.example.cz", "token-A")[0]
    assert deleted == ["1"]
    assert provider.delete_txt_record_exact("example.cz", "_acme-challenge.example.cz", "missing") == (True, "TXT record is already absent")


@pytest.mark.parametrize("status,message", [(401, "Invalid ACTIVE24 credentials"), (403, "Invalid ACTIVE24 credentials"),
                                             (429, "ACTIVE24 API rate limit reached"), (500, "ACTIVE24 API error")])
def test_http_errors_are_safe(provider, monkeypatch, status, message):
    provider.session.request = Mock(return_value=Response(status, {}))
    ok, _, result = provider._request("GET", "/v2/check")
    assert not ok and message in result


def test_timeout_and_invalid_json(provider, monkeypatch):
    provider.session.request = Mock(side_effect=requests.Timeout())
    assert provider._request("GET", "/v2/check")[2] == "ACTIVE24 API timeout"
    provider.session.request = Mock(return_value=Response(200, ValueError()))
    assert provider._request("GET", "/v2/check")[2] == "Invalid response from ACTIVE24 API"


def test_connection(provider, monkeypatch):
    def request(method, path, payload=None):
        if path == "/v2/check":
            return True, {"verified": True}, ""
        return True, {"services": [{"domain": "example.cz"}]}, ""
    monkeypatch.setattr(provider, "_request", request)
    assert provider.test_connection() == (True, "Connected to ACTIVE24")
