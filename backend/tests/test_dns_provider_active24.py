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
    assert [(x["label"], x["type"]) for x in schema[:2]] == [("API Key", "text"), ("API Secret", "password")]
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
    assert headers["Date"].endswith("+00:00")


def test_longest_suffix_and_substring_protection(provider, monkeypatch):
    calls = []
    def request(method, path, payload=None):
        calls.append(path)
        if path == "/v1/user/self/service":
            return True, {"items": [{"serviceName": "domain", "name": "example.cz", "id": 7}, {"serviceName": "domain", "name": "sub.example.cz", "id": 9}]}, ""
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
            return True, {"items": [{"serviceName": "domain", "name": "example.cz", "id": 7}]}, ""
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
        return True, {"items": [{"serviceName": "domain", "name": "example.cz", "id": 7}]}, ""
    monkeypatch.setattr(provider, "_request", request)
    assert provider.test_connection() == (True, "Connected successfully to Active24 API")


def test_create_preserves_existing_txt_value_and_uses_active24_payload(provider, monkeypatch):
    records = [{"id": 1, "type": "TXT", "name": "_acme-challenge", "content": "value-A"}]
    requests_seen = []

    def request(method, path, payload=None):
        if path == "/v1/user/self/service":
            return True, {"items": [{"serviceName": "domain", "name": "example.cz", "id": 7}]}, ""
        if method == "GET" and path == "/v2/service/7/dns/record":
            return True, records, ""
        if method == "POST":
            requests_seen.append((path, payload))
            return True, None, ""
        return False, None, "unexpected"

    monkeypatch.setattr(provider, "_request", request)
    assert provider.create_txt_record(
        "example.cz", "_acme-challenge.example.cz", "value-B", ttl=300
    ) == (True, "TXT record created")
    assert records == [{"id": 1, "type": "TXT", "name": "_acme-challenge", "content": "value-A"}]
    assert requests_seen == [(
        "/v2/service/7/dns/record",
        {"type": "TXT", "name": "_acme-challenge", "content": "value-B", "ttl": 300},
    )]


def test_connection_rejects_account_without_domain_services(provider, monkeypatch):
    monkeypatch.setattr(provider, "_request", lambda *_: (True, {"items": []}, ""))
    assert provider.test_connection() == (False, "ACTIVE24 account has no available DNS zones")


@pytest.mark.active24_live
@pytest.mark.skipif(
    not all(__import__("os").environ.get(name) for name in (
        "ACTIVE24_API_KEY", "ACTIVE24_API_SECRET", "ACTIVE24_TEST_ZONE"
    )),
    reason="requires explicitly supplied Active24 test credentials and zone",
)
def test_active24_live_create_and_cleanup():
    import os
    import uuid

    zone = os.environ["ACTIVE24_TEST_ZONE"].rstrip(".")
    provider = Active24DnsProvider({
        "api_key": os.environ["ACTIVE24_API_KEY"],
        "api_secret": os.environ["ACTIVE24_API_SECRET"],
    })
    label = f"_ucm-test-{uuid.uuid4().hex[:12]}"
    record_name = f"{label}.{zone}"
    value = f"ucm-{uuid.uuid4().hex}"
    try:
        success, message = provider.create_txt_record(zone, record_name, value)
        assert success, message
        resolved = provider._resolve(zone)
        assert resolved is not None
        records, message = provider._records(resolved[1])
        assert records is not None, message
        assert any(record.get("name") == label and provider._value(record) == value for record in records)
    finally:
        provider.delete_txt_record_exact(zone, record_name, value)
