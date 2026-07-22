# ACTIVE24 DNS provider

Create an API **Identifier** and **Secret key** in ACTIVE24 administration. In UCM add DNS provider **ACTIVE24**, enter those fields, and use Test connection. The optional API base URL is an advanced test/mock setting only.

DNS-01 and wildcard certificates are supported. The provider chooses the longest ACTIVE24-managed suffix, sends a relative TXT name, leaves pre-existing values intact, and removes only the exact ACME token after validation. Concurrent challenges therefore do not remove each other.

Errors distinguish credentials, API availability/timeout, rate limiting, server errors, invalid API response, and accounts without zones. Credentials and authorization values are never logged. No live ACTIVE24 account was available during development; perform a first DNS-01 test on a disposable zone before production.
