# UCM ACTIVE24 Docker deployment

Requires Linux, Docker Engine with Compose v2, OpenSSL, tar, and sufficient disk space. Docker installation is not part of the script.

Copy `.env.example` to `.env`, set `UCM_FQDN`, then replace placeholders using `openssl rand -hex 32`. Keep `.env` mode 600. Run `./deploy.sh install`; use `status`, `logs`, `backup`, `update <tag>`, and `rollback --yes` thereafter.

Named volumes persist SQLite/data, SoftHSM tokens, and `/etc/ucm` encryption configuration. A backup stops UCM for SQLite consistency and archives the two requested data volumes plus tag/digest metadata. Attach an existing Traefik or Nginx Proxy Manager if desired; no proxy is bundled.

To synchronize: `git fetch upstream`, fast-forward `main` from upstream, push main, then rebase the feature branch. Run the ACTIVE24 tests and Docker build after each sync.
