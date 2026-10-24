# LunaStore support

Account-bound tickets live in PostgreSQL. Public pages use Django session authentication and ordinary
multipart POST forms; JavaScript only checks for changes and refreshes the conversation. No API v1/v2
or Telegram reply webhook is exposed. The original problem-report admin is read-only.

## Enable / deploy

1. Deploy the accompanying LunaSpire changes first: private uploads use independent CDN records and
   disk paths; public hash deduplication excludes private rows. This is required for safe orphan cleanup.
   Then run `python manage.py migrate`. Migration `support.0002` imports existing reports, including soft-deleted
   archives, without notifications. Its reverse is deliberately a no-op to preserve conversations. It
   can be reapplied safely. Hard-deleted reports cannot be recovered.
2. Run `npm run babel:build` and the usual static collection/deployment workflow.
3. Restart web, admin and `run_tasks_worker --continuous`. The worker's one-minute support sweep is
   required for recovery after Redis outages; it also queues orphan-upload cleanup hourly. No new
   process or scheduler is required. All Django services must use the same database/storage secret.
4. The existing `Модераторы` group receives `support.view_ticket` and `support.process_ticket` after
   migration. For another group, assign both explicitly and enable staff access. Read-only staff need
   only `view_ticket`; assignees must have both permissions. Delivery inspection/retry uses these same
   support permissions. Ticket/message deletion and editing sent messages are not exposed.
5. In Constance → «Поддержка», set `SUPPORT_ADMIN_BASE_URL` to the externally reachable **admin service
   origin** (e.g. `https://admin.example.com`, without the admin path). Set `SUPPORT_TELEGRAM_ENABLED=True`
   and configure the existing bot. Optional support chat/topic overrides fall back to the common log
   chat/topic. Telegram delivery starts disabled to avoid sending test events to the team's chat.

`SUPPORT_ENABLED` controls public support pages. Existing conversations remain available to authorized
staff. `SUPPORT_SITE_NOTIFICATIONS_ENABLED` controls LunaSpire alerts. All settings are synchronized to
`.env` by the existing Constance integration. User-facing support counts come from PostgreSQL, so they
continue to work independently of LunaSpire notifications.

## Delivery and operations

Messages, state transitions, audit events and outbox rows commit together. Redis receives only delivery
IDs after commit. A short database lease claims a delivery; no external HTTP call holds a row lock.
Expired leases are retried, with a maximum of five attempts and deferred exponential backoff (Telegram
`retry_after` is honored). Errors omit tokens and external response bodies. Failed/skipped deliveries
can be manually retried in Unfold. Check failed deliveries and the oldest pending `available_at` when
monitoring support. Duplicate external notifications remain possible after a crash following acceptance
by Telegram/LunaSpire; exactly-once external delivery is not promised.

Conversation ordering and duplicate POST handling are serialized per ticket (creation per owner).
Internal notes never advance public revisions or appear in public queries/download routes. Read cursors
advance only to messages included in the rendered page and never backwards. Staff cursors are personal.

## Private attachments

Three PNG/JPEG/TXT/LOG files, up to 5 MiB each. Three separate file controls work in IE6. Django validates
extension and content, then proxies the upload to LunaSpire using a private upload token. Each storage
request has a durable staging row/object key before it starts. The public message is committed only
when every attachment has uploaded. An error leaves the entered text in the form; the user must reselect
files, as browsers prohibit restoring file inputs.

Uploads are bounded at the application layer; configure the reverse proxy's multipart request limit
for at least 15 MiB plus form overhead (16 MiB is sufficient). Files use Django's standard temporary-file
upload handling. Private LunaSpire `storage/` must never be exposed by a static web-server alias. Back up
that storage alongside PostgreSQL. Orphans older than one day are deleted; an uncertain upload is looked
up by its unique object key first. Attached files are retained with the conversation.

Downloads require a fresh ownership/permission check in Django, then redirect to LunaSpire with a
60-second bearer URL. Anyone holding that URL can use it until expiry. No previews or public media
paths are generated; no file body or conversation text is sent to Telegram. Native HTTP support on
legacy operating systems inherits the site's existing transport characteristics.

noSpam rule entrypoints are `support_create` and `support_reply`. Initial write limits are 5 ticket
submissions per account per hour, 10 replies/status writes per account per minute per route, and
20 writes per IP per minute per route. Form views do not consume these limits.

Interface and notification translations are included for ru, en, uk, be and kk. New messages use
stable uppercase IDs (`PAGE_SUPPORT_*`, `FORM_SUPPORT_*`, `ERROR_SUPPORT_*`, `NOTIF_SUPPORT_*`, etc.);
human-readable text belongs in the catalogs’ `msgstr` entries.

## Checks

`python manage.py test apps.support` covers lifecycle, permissions, hidden notes, private attachments,
CSRF, pagination, idempotency, PostgreSQL concurrency, migration and delivery/storage failures.
`python manage.py check`, `python manage.py makemigrations --check --dry-run`, Python style checks and
`npm run babel:build` should pass before deployment. Actual IE6 behavior requires an XP/IE6 VM.
