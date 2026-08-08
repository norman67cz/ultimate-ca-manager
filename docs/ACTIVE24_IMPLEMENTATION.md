# ACTIVE24 implementation

Base: upstream `v2.205` at `54a3d3782`.

Providers are registered in `dns_providers/__init__.py`; UCM renders credential forms from `get_credential_schema()` and persists encrypted provider credentials. ACME proxy records domain, record name, challenge value, and provider ID in `dns_records_created`. Cleanup may create a fresh provider instance.

This independent Python implementation follows the public ACTIVE24 REST API contract. It does not use acme.sh code or runtime dependencies. Requests use UTC HMAC-SHA1 signing, safe timeouts, and limited retry only for GET/DELETE. The zone algorithm normalizes IDN/wildcards and selects the longest label-boundary suffix.
