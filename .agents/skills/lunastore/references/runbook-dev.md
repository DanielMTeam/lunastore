# Development, Run, and Ops Runbook

Local setup, Docker Compose, migrations, testing, localization, and common troubleshooting for **LunaStore**.

---

## Quick start

### Option 1: Automated install (Docker)
- **Windows (PowerShell):**
  ```powershell
  .\setup.ps1
  ```
- **Linux / macOS (Bash):**
  ```bash
  chmod +x setup.sh
  ./setup.sh
  ```
The script checks Docker, creates `.env` from `.env.example`, starts containers, runs migrations, and collects static files.

---

### Option 2: Local Windows without Docker (`run-dev.ps1`)
```powershell
# Instant start (no checks, installs, or migrations):
.\run-dev.ps1 fast

# Full start with checks, Babel, and migrations:
.\run-dev.ps1 start

# Aliases for start: quick | run | up
.\run-dev.ps1 status
.\run-dev.ps1 stop
.\run-dev.ps1 restart
.\run-dev.ps1 migrate
.\run-dev.ps1 makemigrations
.\run-dev.ps1 install
.\run-dev.ps1 build-js
.\run-dev.ps1 watch-js
.\run-dev.ps1 test
.\run-dev.ps1 superuser
```
Creates `.venv` if needed, installs from `requirements.txt` when required, checks PostgreSQL (`5432`) and Redis (`6379`), compiles JS, and opens titled consoles for web (`9088`), admin (`8088`), API (`7088`), Babel watcher, and LunaSpire (`8080` locally).

---

### Option 3: Manual Docker Compose (Linux / servers)

1. **Environment file:**
   ```bash
   cp .env.example .env
   # Edit DB_PASSWORD, SECRET_KEY, ADMIN_URL as needed
   ```

2. **Local Python & Node (IDE / linters):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
   pip install -r requirements.txt
   npm install
   ```

3. **Build and start:**
   ```bash
   make dev-build
   make dev-up
   ```

4. **Migrate and create superuser:**
   ```bash
   make dev-migrate
   make dev-superuser
   ```

5. **Compile JS for IE6:**
   ```bash
   npm run babel:build
   ```

---

## Makefile reference

### Development (`docker-compose.dev.yml`)

| Command | Description |
| :--- | :--- |
| `make dev-up` | Start services in background (`web:9088`, `admin:8088`, `api:7088`, `lunaspire:6080`, `db`, `redis`) |
| `make dev-down` | Stop and remove dev containers |
| `make dev-restart` | Restart all containers |
| `make dev-logs` | Follow combined logs |
| `make dev-build` | Rebuild images |
| `make dev-makemigrations` | Create migrations via `web` |
| `make dev-migrate` | Apply migrations on `web`, `admin`, and `api` |
| `make dev-superuser` | Interactive Django superuser |
| `make dev-collectstatic` | Collect static files |
| `make dev-test` | Run Django tests |
| `make dev-shell-web` | Shell in `lunastore_web` |
| `make dev-shell-admin` | Shell in `lunastore_admin` |
| `make dev-shell-api` | Shell in `lunastore_api` |

### Optional analytics (ClickHouse)

| Command | Description |
| :--- | :--- |
| `make dev-analytics-up` | Start ClickHouse (`profiles: ["analytics"]`) |
| `make dev-analytics-down` | Stop analytics containers |
| `make dev-analytics-logs` | Tail analytics logs |
| `make dev-analytics-migrate` | Run analytics schema migrations |
| `make dev-analytics-ping` | Connectivity / health check |

Production-style aliases without the `dev-` prefix also exist (`make up`, `make analytics-up`, etc.).

---

### JavaScript / IE6 compile

| Command | Description |
| :--- | :--- |
| `npm run babel:build` | Transpile `staticfiles/js/` → `static/js/` for IE6 |
| `npm run babel:watch` | Watch `staticfiles/js/` |
| `make js-install` | Install npm deps (`@babel/core`, `@babel/preset-env`, …) |
| `make js-build` / `make js-watch` | Makefile wrappers for Babel |

---

### Localization (i18n) and Tolgee

| Command | Description |
| :--- | :--- |
| `make i18n-make` | `makemessages -a` for `.po` files |
| `make i18n-compile` | `compilemessages` for `.mo` |
| `make tolgee-push` | Push new keys to Tolgee |
| `make tolgee-pull` | Pull translations from Tolgee |
| `make i18n-sync` | Full cycle: make → push → pull → compile |

Languages: `ru`, `en`, `uk`, `be`, `kk`.

---

### Lint

```bash
pycodestyle . --exclude=.venv,venv,migrations,.git --max-line-length=120
```

---

## Troubleshooting

### 1. Database connection errors on startup
- **Symptom:** `psycopg.OperationalError: could not connect to server`.
- **Cause:** PostgreSQL still initializing when Django starts.
- **Fix:** Compose uses a `pg_isready` healthcheck. Wait a few seconds or `make dev-restart`.

### 2. JS changes not visible in the browser
- **Cause:** Edited `staticfiles/js/` without Babel.
- **Fix:** `npm run babel:build` (or `.\run-dev.ps1 watch-js`), then `make dev-collectstatic` if needed.

### 3. Sentry / GlitchTip smoke test
```bash
docker compose -f docker-compose.dev.yml exec web python manage.py sentry_test
```

### 4. Cleanup of stale data
```bash
docker compose -f docker-compose.dev.yml exec web python manage.py clear_trash
```

### 5. Analytics disabled
- Ensure `ANALYTICS_ENABLED=True` in Constance / `.env`, then `make dev-analytics-up` and `make dev-analytics-migrate`.
- `make dev-analytics-ping` verifies connectivity.
