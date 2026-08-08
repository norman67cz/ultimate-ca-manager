# UCM ACTIVE24 Docker deployment

Requires Linux, Docker Engine with Compose v2, OpenSSL, tar, and sufficient disk space. Docker installation is not part of the script.

Copy `.env.example` to `.env`, set `UCM_FQDN`, then replace placeholders using `openssl rand -hex 32`. Keep `.env` mode 600. Run `./deploy.sh install`; use `status`, `logs`, `backup`, `update <tag>`, and `rollback --yes` thereafter.

Named volumes persist SQLite/data, SoftHSM tokens, and `/etc/ucm` encryption configuration. A backup stops UCM for SQLite consistency and archives the two requested data volumes plus tag/digest metadata. Attach an existing Traefik or Nginx Proxy Manager if desired; no proxy is bundled.

## Synchronizace s upstreamem

Vývojový počítač musí mít čistý pracovní strom. Produkční server pouze stahuje verzovanou image z GHCR; neprovádí Git operace.

```bash
git fetch upstream --tags
git checkout main
git merge --ff-only upstream/main
git push origin main

git checkout feature/dns-active24
git rebase main
```

Při konfliktu opravte pouze zamýšlené překrytí, pak použijte `git add <soubor>` a `git rebase --continue`. Pro návrat použijte `git rebase --abort`. Po úspěšném rebase zkontrolujte `git diff main...HEAD`, spusťte ACTIVE24/ACME testy i Docker build a feature větev publikujte bezpečně:

```bash
git push --force-with-lease origin feature/dns-active24
git tag -a active24-v<upstream>.1 -m "ACTIVE24 image release"
git push origin active24-v<upstream>.1
```

Tag je neměnný. V produkci nejprve proveďte backup, změňte pouze konkrétní `UCM_IMAGE_TAG`, stáhněte image a recreate pouze služby `ucm`. Předchozí tag ponechte jako rollback cíl; nepoužívejte `latest`, `git push --force` ani `docker compose down -v`.
