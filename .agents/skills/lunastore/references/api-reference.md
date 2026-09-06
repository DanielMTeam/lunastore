# API Reference: V1 (`/method/`) and V2 REST (`/v2/`)

Structure, response formats, authentication, throttling, and batching for the LunaStore API.

---

## Architecture overview

LunaStore exposes two API modes:

1. **V1 Legacy RPC (`/method/`)**:
   - Implemented in [`apps/api/views.py`](../../../apps/api/views.py).
   - Call format: `/method/<resource>/<action>/` (DRF `@action` `url_path` values).
   - Suited to lightweight and retro desktop clients (C++/VB/Delphi on Windows XP).
2. **V2 Modern REST (`/v2/`)**:
   - Implemented in [`apps/api/v2/views.py`](../../../apps/api/v2/views.py).
   - Django REST Framework + JWT (`SimpleJWT`).
   - Supports `ExecuteView` batching, DRF serializers, and OpenAPI 3.0 via `drf-spectacular`.

Primary mount: API container on port `7088` (`lunastore.urls_api`). `/method/` is also included on web and admin URLConfs.

---

## Authentication and API security

### 1. JWT authentication (V2)
- **Obtain token (login):**
  `POST /v2/auth/token/`
  ```json
  {
    "username": "user",
    "password": "password"
  }
  ```
  Response: `{"access": "<JWT>", "refresh": "<JWT>"}`. TOTP-enabled users may need `totp_code`.
- **Refresh:**
  `POST /v2/auth/token/refresh/`
  ```json
  {
    "refresh": "<JWT>"
  }
  ```
- **Revoke (logout):**
  `POST /v2/auth/token/revoke/` (blacklist).
- **Requests:** `Authorization: Bearer <access_token>`.

### 2. Throttling
- Controlled in `apps/api/throttling.py` with Constance limits:
  - `API_THROTTLE_ENABLED`
  - `API_THROTTLE_ANON_RATE` (default `1000/hour`)
  - `API_THROTTLE_USER_RATE` (default `5000/hour`)
- Exceeding limits returns HTTP 429.

---

## V1 Legacy RPC (`/method/`)

### Response formats
Success:
```json
{
  "response": {
    "id": 1,
    "title": "Total Commander",
    "version": "11.03"
  }
}
```

Error (`LunaException` / `apps/api/handlers.py`):
```json
{
  "error": {
    "error_code": 1001,
    "error_msg": "'ID' field missing",
    "request_params": {
      "method": "user.getProfileInfo"
    }
  }
}
```

### Main V1 actions
Paths are slash-separated (trailing slash as configured by Django):

| Path | HTTP | Description | Typical params |
| :--- | :--- | :--- | :--- |
| `/method/user/getProfileInfo/` | GET | Public user profile | `id` |
| `/method/user/getPublicUploadToken/` | GET | Public LunaSpire upload JWT | auth as required |
| `/method/user/getPrivateUploadToken/` | GET | Private upload JWT | auth as required |
| `/method/user/getNotificationToken/` | GET | Notification receive token | auth as required |
| `/method/marketplace/getAppInfo/` | GET | Application details | `id` |
| `/method/marketplace/search/` | GET | Trigram search | `q`, `limit`, `offset` |
| `/method/category/getAppList/` | GET | Apps in a category | category id param |
| `/method/distribution/getDistributionsList/` | GET | Distributions for an app | app id param |
| `/method/service/heartbeat/` | GET | Health / heartbeat | — |
| `/method/service/developersList/` | GET | Developers list | — |
| `/method/service/kunyakin/` | GET | Service easter-egg / status helper | — |

There is no V1 `getDownloadLink` action; downloads go through the web `/get_dist_file/<id>/` → LunaSpire JWT redirect flow.

---

## V2 REST API (`/v2/`)

### ViewSets and endpoints

Most marketplace resources are **read-only** ViewSets.

| Endpoint | Methods | Description |
| :--- | :--- | :--- |
| `/v2/marketplace/` | GET | Published apps (pagination, filters) |
| `/v2/marketplace/{id}/` | GET | App detail (screenshots, reviews context) |
| `/v2/marketplace/search/` | GET | Fuzzy trigram search (`?q=winamp`) |
| `/v2/category/` | GET | Category list |
| `/v2/category/{id}/` | GET | Category detail |
| `/v2/category/{id}/apps/` | GET | Apps in category |
| `/v2/distribution/{id}/` | GET | Distribution detail |
| `/v2/distribution/by_app/` | GET | Distributions for an application |
| `/v2/collection/` | GET | Public collections (read-only) |
| `/v2/collection/{id}/` | GET | Collection detail |
| `/v2/collection/{id}/apps/` | GET | Apps in collection |
| `/v2/collection/by_user/` | GET | Collections owned by a user |
| `/v2/user/{id}/` | GET | Public user profile |
| `/v2/user/getPublicUploadToken/` | GET | Public upload JWT (auth) |
| `/v2/user/getPrivateUploadToken/` | GET | Private upload JWT (auth) |
| `/v2/user/getNotificationToken/` | GET | Notification token (auth) |
| `/v2/service/heartbeat/` | GET | Healthcheck |
| `/v2/service/developersList/` | GET | Developers list |
| `/v2/service/kunyakin/` | GET | Service helper |

There is no `/v2/distribution/{id}/download_token/`, no write CRUD on collections, and no `/v2/service/status/`.

---

## Batch execution: `ExecuteView` (`/v2/execute/`)

`ExecuteView` batches up to **25** API method calls in one POST (similar to VK `execute`).

### Request
`POST /v2/execute/`
```json
{
  "code": [
    {
      "method": "category.list",
      "params": {}
    },
    {
      "method": "marketplace.retrieve",
      "params": { "pk": 42 }
    },
    {
      "method": "collection.by_user",
      "params": { "user_id": 1 }
    }
  ]
}
```

- Body key is **`code`** (not `methods`).
- Method names map to ViewSet actions such as `list`, `retrieve`, `search`, `apps`, `by_app`, `by_user`.

### Response
```json
{
  "responses": [
    { "...": "per-call success or error payload" },
    { "error_code": 4005, "error_msg": "..." }
  ]
}
```

Each entry under `responses` is the decoded body of the internal call. Unknown methods yield `error_code` `4005` (`METHOD_NOT_FOUND`) while the outer HTTP status remains 200.

---

## Interactive docs (Swagger / OpenAPI)

On the `api` container (port `7088`):
- **OpenAPI 3.0 schema:** `/schema/`
- **Swagger UI:** `/` (API service root)
- Schema generated by `drf-spectacular` from `@extend_schema` annotations.
