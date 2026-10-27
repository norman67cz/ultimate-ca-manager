"""A single-label Local Domains entry is a suffix, not an identifier."""

from api.acme.acme_api import validate_local_acme_identifier
from api.v2.acme_local_domains import _is_valid_domain


def test_private_suffix_validation():
    for value in ('homeland', 'corp', 'lan.homeland', 'example.cz'):
        assert _is_valid_domain(value)
    for value in ('.homeland', 'homeland.', 'foo..homeland', 'home_land',
                  '-home', 'home-', 'http://homeland', 'home land'):
        assert not _is_valid_domain(value)


def test_local_identifier_requires_fqdn():
    for value in ('pve01.homeland', 'foo.bar.homeland', '*.homeland'):
        assert validate_local_acme_identifier({'type': 'dns', 'value': value})[0]
    assert not validate_local_acme_identifier({'type': 'dns', 'value': 'homeland'})[0]
