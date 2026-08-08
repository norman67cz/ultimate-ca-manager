# UCM ACTIVE24 fork — agent instructions

## Scope

This fork adds the native ACTIVE24 DNS provider to Ultimate Certificate Manager (UCM). Keep changes focused on the requested feature; do not perform unrelated refactors or reformatting.

## Git workflow

- `origin` is the `norman67cz/ultimate-ca-manager` fork; `upstream` is `NeySlim/ultimate-ca-manager`.
- Develop ACTIVE24 changes on `feature/dns-active24`.
- Before changing shared history, ensure the worktree is clean and create a local backup branch when appropriate.
- Update the fork base with `git fetch upstream --tags`, fast-forward `main` from `upstream/main`, then rebase `feature/dns-active24` on `main`.
- Publish a rebased shared feature branch only with `git push --force-with-lease`; never use plain `--force`.
- Do not rewrite published `active24-v*` release tags.

## ACTIVE24 provider requirements

- Implement the provider natively in Python under `backend/services/acme/dns_providers/active24.py`.
- Do not invoke `acme.sh`, copy GPL code, or use shell hooks at runtime.
- Use the ACTIVE24 REST API with HTTPS verification, bounded timeouts, and limited retries only for safe operations.
- Preserve the exact DNS-01 cleanup contract: delete only a TXT record matching zone, relative name, type, and challenge value. Never delete all `_acme-challenge` records at a name.
- Do not log API secrets, Authorization headers, credentials dictionaries, or full DNS challenge values.
- Keep provider credentials in UCM's existing encrypted storage and use password fields in the dynamic credential schema.

## Verification

Run the relevant checks after provider or ACME changes:

```bash
docker run --rm \
  -v "$PWD/backend:/opt/ucm/backend" \
  --entrypoint /opt/ucm/venv/bin/pytest \
  ghcr.io/norman67cz/ultimate-ca-manager-active24:<verified-tag> \
  /opt/ucm/backend/tests/test_dns_provider_active24.py \
  /opt/ucm/backend/tests/test_acme_renewal_dns_cleanup.py \
  /opt/ucm/backend/tests/test_acme_proxy_issue_fixes.py -q

git diff --check
```

Run an opt-in live ACTIVE24 test only with explicitly supplied test credentials and a disposable test record; never commit those credentials.

## Docker and release workflow

- Build the frontend as production Vite assets; the runtime image must serve `/opt/ucm/frontend/dist`, not `/src/main.jsx`.
- Do not use `latest` for production images.
- Release image tags follow `active24-v<upstream-version>.<patch>` (for example `active24-v2.206.2`).
- A release tag triggers `.github/workflows/build-active24-image.yml`, which builds and pushes `linux/amd64` to GHCR.
- Verify the GitHub Actions result before recommending a new image tag for production.
- On production, preserve named volumes and recreate only `ucm`; do not use `docker compose down -v`.

## Secrets and deployment files

- Never commit `.env`, API keys, secrets, certificates, database files, backup archives, or Docker volume contents.
- Keep deployment secrets in a root/user-readable-only `.env` or an external secret manager.
- `/etc/ucm` must be backed by a persistent mount/volume before requiring private-key encryption.
- Changing `UCM_DB_ENCRYPTION_KEY` requires a planned migration/re-entry of existing integration credentials; do not replace it blindly.
