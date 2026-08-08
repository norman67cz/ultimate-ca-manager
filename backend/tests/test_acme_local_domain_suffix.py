"""Regression tests for Local Domains internal suffix policies."""

from api.acme.acme_api import validate_acme_identifier
from api.v2.acme_local_domains import _is_valid_domain


def test_single_label_local_domain_policy_suffixes():
    assert _is_valid_domain("homeland")
    assert _is_valid_domain("lan.homeland")
    assert _is_valid_domain("example.cz")
    assert not _is_valid_domain(".homeland")
    assert not _is_valid_domain("*.homeland")
    assert not _is_valid_domain("home_land")
    assert not _is_valid_domain("homeland.")
    assert validate_acme_identifier({"type": "dns", "value": "pve01.homeland"})[0]
    assert validate_acme_identifier({"type": "dns", "value": "*.homeland"})[0]
    assert not validate_acme_identifier({"type": "dns", "value": "homeland"})[0]
