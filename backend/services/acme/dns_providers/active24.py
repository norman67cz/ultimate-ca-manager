"""ACTIVE24 DNS provider, independently implemented from its public REST API."""
import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseDnsProvider

logger = logging.getLogger(__name__)


class Active24DnsProvider(BaseDnsProvider):
    PROVIDER_TYPE = "active24"
    PROVIDER_NAME = "ACTIVE24"
    PROVIDER_DESCRIPTION = "ACTIVE24 DNS API"
    REQUIRED_CREDENTIALS = ["api_key", "api_secret"]
    OPTIONAL_CREDENTIALS = ["api_base_url"]
    DEFAULT_BASE_URL = "https://rest.active24.cz"
    TIMEOUT = (5, 30)

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = str(credentials.get("api_base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        self._zones: Dict[str, Tuple[str, str]] = {}
        self.session = requests.Session()
        retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=.3,
                      allowed_methods=frozenset(("GET", "DELETE")),
                      status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    @staticmethod
    def _domain(value: str) -> str:
        value = value.lower().rstrip(".")
        return (value[2:] if value.startswith("*.") else value).encode("idna").decode("ascii")

    @staticmethod
    def _canonical_string(method: str, path: str, timestamp: int) -> str:
        return f"{method.upper()} {urlsplit(path).path} {timestamp}"

    def _headers(self, method: str, path: str, timestamp: Optional[int] = None) -> Dict[str, str]:
        timestamp = int(time.time()) if timestamp is None else timestamp
        canonical = self._canonical_string(method, path, timestamp)
        sig = hmac.new(self.credentials["api_secret"].encode(), canonical.encode(), hashlib.sha1).hexdigest()
        auth = base64.b64encode(f"{self.credentials['api_key']}:{sig}".encode()).decode()
        return {"Date": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                "Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Basic {auth}"}

    def _request(self, method, path, payload=None):
        try:
            response = self.session.request(method, f"{self.base_url}{path}", headers=self._headers(method, path),
                                            json=payload, timeout=self.TIMEOUT)
        except requests.Timeout:
            return False, None, "ACTIVE24 API timeout"
        except requests.RequestException as exc:
            logger.warning("ACTIVE24 API request failed: %s", self.redact_secrets(exc))
            return False, None, "ACTIVE24 API is unavailable"
        if response.status_code in (401, 403):
            return False, None, "Invalid ACTIVE24 credentials"
        if response.status_code == 429:
            return False, None, "ACTIVE24 API rate limit reached"
        if response.status_code >= 400:
            logger.warning("ACTIVE24 API returned HTTP %s", response.status_code)
            return False, None, f"ACTIVE24 API error (HTTP {response.status_code})"
        if not response.content:
            return True, None, ""
        try:
            return True, response.json(), ""
        except ValueError:
            return False, None, "Invalid response from ACTIVE24 API"

    @staticmethod
    def _items(data):
        if isinstance(data, dict):
            yield data
            for value in data.values():
                yield from Active24DnsProvider._items(value)
        elif isinstance(data, list):
            for value in data:
                yield from Active24DnsProvider._items(value)

    def _resolve(self, domain):
        name = self._domain(domain)
        if name in self._zones:
            return self._zones[name]
        ok, services, _ = self._request("GET", "/v1/user/self/service")
        if not ok:
            return None
        zones = []
        for item in self._items(services):
            zone = item.get("zone") or item.get("domain") or item.get("name")
            if isinstance(zone, str) and "." in zone:
                zone = self._domain(zone)
                if name == zone or name.endswith("." + zone):
                    zones.append(zone)
        if not zones:
            return None
        zone = max(zones, key=len)
        ok, detail, _ = self._request("GET", f"/v1/user/self/zone/{zone}")
        if not ok:
            return None
        service_id = next((item.get("service_id") or item.get("serviceId") or item.get("id")
                           for item in self._items(detail)
                           if item.get("service_id") or item.get("serviceId") or item.get("id")), None)
        if service_id is None:
            return None
        self._zones[name] = (zone, str(service_id))
        return self._zones[name]

    def get_zone_for_domain(self, domain):
        result = self._resolve(domain)
        return result[0] if result else None

    def _records(self, service_id):
        ok, data, message = self._request("GET", f"/v2/service/{service_id}/dns/record")
        if not ok:
            return None, message
        if isinstance(data, list):
            return data, ""
        if isinstance(data, dict):
            return next((data[key] for key in ("records", "data", "items") if isinstance(data.get(key), list)), []), ""
        return [], ""

    @staticmethod
    def _value(record):
        return record.get("content", record.get("value"))

    def _relative(self, record_name, zone):
        return self.get_relative_record_name(self._domain(record_name), zone).rstrip(".")

    def create_txt_record(self, domain, record_name, record_value, ttl=300):
        resolved = self._resolve(domain)
        if not resolved:
            return False, "No ACTIVE24 DNS zone is available for this domain"
        zone, service_id = resolved
        name = self._relative(record_name, zone)
        records, message = self._records(service_id)
        if records is None:
            return False, message
        if any(r.get("type") == "TXT" and r.get("name") == name and self._value(r) == record_value for r in records):
            return True, "TXT record already exists"
        ok, _, message = self._request("POST", f"/v2/service/{service_id}/dns/record",
                                       {"type": "TXT", "name": name, "content": record_value, "ttl": max(300, int(ttl))})
        return (True, "TXT record created") if ok else (False, message)

    def delete_txt_record(self, domain, record_name):
        return self.delete_txt_record_exact(domain, record_name)

    def delete_txt_record_exact(self, domain, record_name, record_value=None):
        resolved = self._resolve(domain)
        if not resolved:
            return True, "TXT record is already absent"
        zone, service_id = resolved
        name = self._relative(record_name, zone)
        records, message = self._records(service_id)
        if records is None:
            return False, message
        matches = [r for r in records if r.get("type") == "TXT" and r.get("name") == name
                   and (record_value is None or self._value(r) == record_value)]
        for record in matches:
            record_id = record.get("id") or record.get("record_id")
            if record_id is None:
                continue
            ok, _, message = self._request("DELETE", f"/v2/service/{service_id}/dns/record/{record_id}")
            if not ok:
                return False, message
        return True, "TXT record deleted" if matches else "TXT record is already absent"

    def test_connection(self):
        ok, data, message = self._request("GET", "/v2/check")
        if not ok:
            return False, message
        if not isinstance(data, dict) or data.get("verified") is not True:
            return False, "Invalid response from ACTIVE24 API"
        ok, services, _ = self._request("GET", "/v1/user/self/service")
        if not ok or not any(True for _ in self._items(services)):
            return False, "ACTIVE24 account has no available DNS zones"
        return True, "Connected to ACTIVE24"

    @classmethod
    def get_credential_schema(cls):
        return [{"name": "api_key", "label": "Identifier", "type": "text", "required": True},
                {"name": "api_secret", "label": "Secret key", "type": "password", "required": True},
                {"name": "api_base_url", "label": "API base URL (advanced)", "type": "text", "required": False,
                 "default": cls.DEFAULT_BASE_URL}]
