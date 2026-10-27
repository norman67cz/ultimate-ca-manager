# ACTIVE24 fork implementation (UCM v2.245)

This release branch starts at upstream `v2.245`, commit
`e2778d83473a7c815262bbfd54887861b0179bc3`. The provider is implemented
independently in Python against the public ACTIVE24 REST API contract; no
`acme.sh` code or runtime dependency is included.

`Active24DnsProvider` is registered in the existing DNS provider registry.
Its credential schema drives the normal UI fields (API Key and masked API
Secret), and UCM's provider storage encrypts the credentials. The provider
uses HMAC-SHA1 signed ACTIVE24 requests, discovers the longest available DNS
zone, and creates a relative TXT record without replacing other values.
Cleanup receives the challenge value through the backward-compatible
`delete_txt_record_exact` hook, so a freshly constructed provider can delete
only the matching TXT value. The outbound ACME client and ACME proxy both use
this hook. Provider errors stop challenge submission and never include API
credentials. Propagation continues to use UCM's existing DNS polling.

The branch also makes a single-label Local ACME Allowed Domains entry (such
as `homeland`) a policy suffix for names below it. Bare `homeland` remains an
invalid Local ACME certificate identifier. This change does not alter the
external ACME client or proxy identifier rules, and needs no DB migration.

The Docker image builds Vite assets from the same source revision as the
backend. Build it with `--build-arg VCS_REF=<commit>` and an immutable tag.
The fork's GitHub Actions workflow publishes to GHCR only from the fork.
