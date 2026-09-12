# LunaStore — Development Guide & Rules for AI Agents (AGENTS.md)

> **LunaStore** is an application catalog and retro ecosystem for legacy operating systems (Windows XP, 2000, 98), optimized to run even in **Internet Explorer 6**, on a modern backend stack.
>
> Developers: **DM Team (fayzetwin & team)**.

---

## Quick project context

| Component | Technologies / Stack | Details |
| :--- | :--- | :--- |
| **Backend** | Python 3.13 / Django 6.1.1, DRF 3.18.1 | Clean architecture under `apps/` (`core`, `user`, `marketplace`, `api`, `terms`, `analytics`) |
| **Database** | PostgreSQL 18 | `pg_trgm` (GIN trigram search), `django-safedelete` |
| **Cache & Throttling** | Redis 7 | `django-redis`, `django-smart-ratelimit`, `django-constance[redis]` |
| **Analytics (optional)** | ClickHouse | Compose profile `analytics`; `apps/analytics`; gated by `ANALYTICS_ENABLED` |
| **Storage & CDN** | **LunaSpire** (Go engine) | Host `6080` → container `8080`. File storage, CDN, push notifications, JWT tokens |
| **Admin Panel** | `django-unfold` | Port `8088` (`urls_private.py`). Moderation, Constance, noSpam under `/${ADMIN_URL}/` |
| **Frontend** | HTML5/HTML4 + Vanilla CSS + ES5 (Babel) | Windows XP / Luna retro design. **Internet Explorer 6** support |
| **API** | REST (DRF) + RPC v1 | `/method/` (v1 legacy RPC) and `/v2/` (JWT, OpenAPI Swagger, Execute batching) |
| **Auth & Security** | OIDC (Authentik) + Native + TOTP 2FA | noSpam engine, MX/disposable email validation, IP/User bans, sessions |
| **Error Tracking** | Sentry / GlitchTip | Configured via `.env` and Constance |

---

## Core architectural rules and conventions

### 1. Internet Explorer 6 compatibility (CRITICAL)
- **JS sources live in `staticfiles/js/`**; Babel-compiled output lives in `static/js/`.
- Never use modern browser APIs (`fetch`, `const`/`let` in inline template scripts, arrow functions, `localStorage`, `async`/`await`) directly in HTML templates without fallbacks or Babel transpilation.
- For LunaSpire CDN images and links, use **protocol-relative URLs** (e.g. `//spire.lunastore.app/file`) to avoid SSL/mixed-content issues on legacy OSes.
- PNG transparency in IE6 is handled via `dd_belatedpng.min.js`.
- After editing JS under `staticfiles/js/`, always compile: `npm run babel:build`.

### 2. Service split (Docker & URLConfs)
In the dev environment (`docker-compose.dev.yml`) the app runs as three Django containers with different `ROOT_URLCONF` values:
1. `web` (port `9088`): `lunastore.urls` — main user-facing UI (`.php`-style routes such as `index.php`, `app.php`).
2. `admin` (port `8088`): `lunastore.urls_private` — admin/moderator panel (`/${ADMIN_URL}/`, `/${ADMIN_URL}/broadcast/`, `/${ADMIN_URL}/nospam/mass-scan/`).
3. `api` (port `7088`): `lunastore.urls_api` — `/method/`, `/v2/`, `/schema/`, Swagger UI.

Note: `/method/` is also mounted on the web and admin URLConfs; the dedicated API service on `:7088` is the primary API surface.

### 3. Models and deletion (Soft Delete)
- Many marketplace and user models inherit from `SafeDeleteModel` (`_safedelete_policy = SOFT_DELETE` or `SOFT_DELETE_CASCADE`).
- Soft delete sets a `deleted` timestamp instead of removing the row. Prefer `.all()` vs `.all_with_deleted()` / `.deleted_only()` accordingly.
- Not every model soft-deletes. Examples without `SafeDeleteModel`: `Badge`, `Review`, `InviteToken`, `UserSession`, `NoSpamRule` / `NoSpamEvent`, `Banner`, `LegalDocument`.

### 4. Internationalization (i18n)
- Uses `django-modeltranslation`. Language fields use codes **`ru`, `en`, `uk`, `be`, `kk`** (e.g. `title_ru`, `title_en`, …, `title_kk`). Category uses `name_*` rather than `title_*`.
- When changing translatable model fields, update the matching `translation.py`.
- Template/message localization uses `{% trans %}` / `gettext_lazy` and syncs with Tolgee (`make i18n-sync`).

### 5. Dynamic configuration (Constance & .env)
- Site settings are managed via `django-constance` (`from constance import config`).
- Admin changes sync back into the `.env` file via `apps/core/constance_sync.py`.

### 6. Anti-spam and moderation (noSpam)
- `apps/user/services/antispam.py` implements a flexible `NoSpamRule` engine (CIDR IP, email/username/UA regex, GeoIP countries, rate signals).
- App/distribution publish and edit requests go through mandatory moderation (`AppCreateRequests`, `DistributionCreateRequests`, etc.) with Telegram notifications to moderators.
- IP ban checks use Redis key `banned_ips_list` and are enforced from views/forms via `BlockBannedIP` helpers — **`BlockBannedIP` is not in global `MIDDLEWARE`**.

### 7. Python code style
- Follow `pycodestyle` with max line length **120**:
  `pycodestyle . --exclude=.venv,venv,migrations,.git --max-line-length=120`
- Ignored codes: `E501`, `W503`, `W504` (see `setup.cfg`).

---

## Useful commands (cheatsheet)

```bash
# === Development (Docker Compose Dev) ===
make dev-up               # Start containers (db, redis, lunaspire, web, admin, api)
make dev-down             # Stop containers
make dev-build            # Rebuild images
make dev-restart          # Restart all containers
make dev-makemigrations   # Create migrations
make dev-migrate          # Apply migrations on all Django services
make dev-collectstatic    # Collect static files
make dev-superuser        # Create Django superuser
make dev-test             # Run Django tests
make dev-logs             # Tail logs

# === Optional analytics (ClickHouse profile) ===
make dev-analytics-up     # Start ClickHouse (compose profile analytics)
make dev-analytics-migrate
make dev-analytics-ping

# === Local Windows run (WITHOUT Docker) ===
.\run-dev.ps1 fast        # Instant start (no checks, installs, or migrations)
.\run-dev.ps1 start       # Full start with checks, Babel, and migrations
.\run-dev.ps1 stop        # Stop all services
.\run-dev.ps1 restart     # Restart all services
.\run-dev.ps1 status      # Check ports and services
.\run-dev.ps1 install     # Install/update requirements.txt and npm deps
.\run-dev.ps1 migrate     # Apply migrations
.\run-dev.ps1 build-js    # Babel build for IE6
.\run-dev.ps1 watch-js    # Babel watch mode
.\run-dev.ps1 test        # Run tests
.\run-dev.ps1 superuser   # Create superuser

# === JavaScript & Babel ===
npm run babel:build       # Compile staticfiles/js/ -> static/js/ for IE6
npm run babel:watch       # Babel watcher

# === Localization ===
make i18n-make            # Collect translation strings (makemessages)
make i18n-compile         # Compile .mo files (compilemessages)
make i18n-sync            # Full cycle: make -> push Tolgee -> pull -> compile

# === Linter ===
pycodestyle . --exclude=.venv,venv,migrations,.git --max-line-length=120
```

---

## Documentation navigation (skill & references)

The detailed agent guide is structured as a built-in skill:

- **Main skill**: [`.agents/skills/lunastore/SKILL.md`](.agents/skills/lunastore/SKILL.md)
- **Architecture & services**: [`.agents/skills/lunastore/references/architecture.md`](.agents/skills/lunastore/references/architecture.md)
- **Django backend & apps**: [`.agents/skills/lunastore/references/backend-django.md`](.agents/skills/lunastore/references/backend-django.md)
- **API v1 (`/method/`) and API v2**: [`.agents/skills/lunastore/references/api-reference.md`](.agents/skills/lunastore/references/api-reference.md)
- **Frontend & IE6 compatibility**: [`.agents/skills/lunastore/references/frontend-ie6.md`](.agents/skills/lunastore/references/frontend-ie6.md)
- **Security, noSpam & sessions**: [`.agents/skills/lunastore/references/security-nospam.md`](.agents/skills/lunastore/references/security-nospam.md)
- **Run & debug instructions**: [`.agents/skills/lunastore/references/runbook-dev.md`](.agents/skills/lunastore/references/runbook-dev.md)
