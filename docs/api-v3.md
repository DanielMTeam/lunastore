# LunaStore API V3

The API host serves the [interactive V3 reference](https://api.lunastore.app/docs/v3/) and the [OpenAPI schema](https://api.lunastore.app/schema/v3/) from the same release as the API. Self-hosted instances should set `API_MEDIA_BASE_URL` to the public origin that serves their static files. Set `API_PUBLIC_SCHEME=https` if TLS terminates upstream and Django receives HTTP. This setting keeps generated pagination and download links on HTTPS.

## Find and download an application

1. Read `GET /v3/platforms/` and choose a supported platform `code`.
2. Read `GET /v3/apps/?q=cleaner&platform=CODE&is_free=true`. Omit `q` to browse. The `category` and `author` filters take numeric IDs. `GET /v3/search/suggestions/?q=clean` returns lightweight app and user suggestions.
3. Open `GET /v3/apps/{id}/` and `GET /v3/apps/{id}/distributions/`. Follow the selected build's `download_url` when present. For private builds, send the bearer token to the LunaStore download endpoint and follow its redirect without forwarding credentials to the file host.
4. Open `GET /v3/categories/` and `GET /v3/categories/{id}/apps/` to browse a category. Its `icon_url` is an absolute URL or `null`. Collections support `GET /v3/collections/?user_id=ID` and `GET /v3/collections/{id}/apps/`.

Lists return `count`, `next`, `previous`, and `results`. The default limit is 20 and the maximum is 100. Follow the provided pagination links. Errors use `application/problem+json` with an HTTP status and a stable `code`. Validation errors also carry an `errors` array with field paths, codes, and messages.

## Sign in and read notifications

1. Post `{"username":"user","password":"…"}` to `/v3/auth/token/`. If the account requires TOTP, repeat with `totp_code`.
2. Set `Authorization: Bearer ACCESS` and call `GET /v3/me/` to read the signed-in user's profile.
3. Poll `GET /v3/me/notifications/?page=1&limit=20` for the inbox and `unread_count`. A notification with `read_at: null` is unread. Send `POST /v3/me/notifications/mark-all-read/` to mark the inbox read. Success returns HTTP 204. On HTTP 429, wait for the duration in `Retry-After`. HTTP 503 means LunaSpire is temporarily unavailable.
4. Post `{"refresh":"…"}` to `/v3/auth/token/refresh/` and replace both saved tokens on success. Post the current refresh token to `/v3/auth/token/revoke/` to end the session.

## Batch catalog requests

Post a JSON body of up to 64 KiB to `/v3/batch/` with 1–25 read operations and at most two distinct searches. Each has a unique client-supplied `id`, an OpenAPI `operationId` in `operation`, and optional scalar `params`. Detail operations take `pk`.

```json
{
  "requests": [
    {"id": "categories", "operation": "v3_categories_list", "params": {"limit": 10}},
    {"id": "versions", "operation": "v3_apps_distributions_list", "params": {"pk": 42}}
  ]
}
```

A valid batch returns HTTP 200 with a `results` array. Each result has `id`, `status`, and `body`. Inspect each status even when the outer request succeeds. Each item counts towards the request limit. Operations that reach the execution deadline report `503` with code `batch_timeout`. Account, token, download, and write operations use their direct routes.

## Migrate from V1

| V1 request under `/method/` | Replacement |
| --- | --- |
| `user/getProfileInfo/?id=ID` | `GET /v3/users/ID/` |
| `user/search/?query=TEXT` | `GET /v3/users/?q=TEXT` |
| `marketplace/getAppInfo/?id=ID` | `GET /v3/apps/ID/` |
| `marketplace/search/?query=TEXT` | `GET /v3/apps/?q=TEXT` |
| `category/getAppList/?id=ID` | `GET /v3/categories/ID/apps/` |
| `distribution/getDistributionsList/?id=ID` | `GET /v3/apps/ID/distributions/` |
| `user/getNotificationToken/` | `GET /v3/me/notifications/` |
| `user/getPublicUploadToken/`, `user/getPrivateUploadToken/` | Existing paths under `/v2/user/` for API clients. LunaStore web uses `/uploads/token/public/` and `/uploads/token/private/`. |
| `service/heartbeat/` | `GET /v3/health/` |
| `service/developersList/`, `service/kunyakin/` | Existing paths under `/v2/service/` |

Read fields directly from a V3 detail response and read list items from `results`. Both `/v2/` and `/method/v2/` expose the existing V2 contract. V2 Execute uses the `code` request key and `responses` result key.

This release removes V1 RPC. Update clients using the table above and point monitoring at the V3 health endpoint. Deploy the matching LunaSpire version first so it accepts the new service token before Django starts sending it. Roll back the application and proxy configuration together if clients need to return to V1.

## V2 compatibility fixes

| Published V2 example or schema | Actual V2 response and correction in this release |
| --- | --- |
| The Execute page shows a top-level array. | V2 wraps it in `{"responses": [...]}`. The generated schema now describes that object. |
| The distribution detail example shows `release_description`. | The V2 serializer returns `lunabox_manifest`, `platform`, and `platforms`. It has no `release_description` field. |
| The search example shows an HTTP `next` link and a protocol-relative `icon_url`. | Set the public scheme behind a proxy so pagination links use HTTPS. V2 retains its media URL format. V3 renders absolute URLs. |
| The search page describes a Meilisearch outage as a `503`. | Both versions try the database fallback when Meilisearch is unavailable. |
| V2 category objects expose the sprite class as `icon`. | V2 keeps `icon` and adds an absolute `icon_url` when a PNG is available. |
| The live OpenAPI describes category and collection app lists as single objects. | The versioned V2 schema describes the paginated app lists and includes the bearer authentication scheme. |

These discrepancies come from the published examples and schema. Use `/schema/v2/` and `/docs/v2/` for the versioned V2 reference. [V2 search](https://docs.lunastore.app/api/marketplace/search/) · [V2 distribution detail](https://docs.lunastore.app/api/distribution/retrieve/) · [V2 Execute](https://docs.lunastore.app/api/execute/) · [Published OpenAPI](https://api.lunastore.app/schema/)

## V2 to V3 request and response examples

Examples use sample records. Excerpts show the fields that matter for migration. The versioned OpenAPI lists all fields.

### Search and pagination

| V2 | V3 |
| --- | --- |
| `GET /method/v2/marketplace/search/?query=cleaner&limit=1` | `GET /v3/apps/?q=cleaner&limit=1` |
| `GET /method/v2/user/search/?query=publisher` | `GET /v3/users/?q=publisher` |
| `GET /method/v2/search/suggest/?query=clean` | `GET /v3/search/suggestions/?q=clean` |

V2 and V3 both return `{count, next, previous, results}` for catalog lists. Use `results` to iterate over items. V1 search used a numbered object such as `{"1":{"id":42,"title":"Cleaner"}}`, with item fields omitted here. In V3 search is optional, so `GET /v3/apps/` also serves as the browse request. Suggestions still group items under `apps` and `users`. Use each item's ID to open its API resource. The web page `url` field is omitted in V3.

**V3 application search response (excerpt)**

```json
{
  "count": 2,
  "next": "https://api.lunastore.app/v3/apps/?limit=1&offset=1&q=cleaner",
  "previous": null,
  "results": [
    {
      "id": 42,
      "title": "Cleaner",
      "version": "1.0",
      "icon_url": "https://spire.lunastore.app/public/cleaner.png",
      "platforms": [{"id": 3, "code": "mobile", "name": "Windows 10 Mobile"}],
      "categories": [
        {
          "id": 9,
          "name": "Utilities",
          "description": "System tools",
          "icon_url": "https://lunastore.app/staticfiles/img/category-icons/util.png",
          "banner_url": null
        }
      ]
    }
  ]
}
```

V3 app cards add `categories` and include `id` in each platform alongside its existing `code` and `name`. Follow `next` as returned so filters and the correct route carry over.

### Category icons and distribution links

| Request | Response fields |
| --- | --- |
| `GET /method/v2/category/9/` | `{"icon":"util","icon_url":"https://lunastore.app/staticfiles/img/category-icons/util.png"}` |
| `GET /v3/categories/9/` | `{"icon_url":"https://lunastore.app/staticfiles/img/category-icons/util.png"}` |
| `GET /method/v2/distribution/17/` | `{"id":17,"app":42,"link":"/get_dist_file/17/","url":"","has_download":true}` |
| `GET /v3/distributions/17/` | `{"id":17,"app":42,"download_url":"https://api.lunastore.app/v3/distributions/17/download/","has_download":true}` |

The V2 category row shows the response after this release. Older V2 responses have only `icon` for the icon. In V3, `icon_url` is `null` for a category without a mapped icon. A distribution with no file has `download_url: null`. When a URL is present, follow its HTTP `302` to download the file. To list builds for an app, move from `GET /method/v2/distribution/by_app/?app_id=42` to `GET /v3/apps/42/distributions/`.

### Errors

**V2 search without its required `query`** returns HTTP `400` with `Content-Type: application/json`.

```json
{
  "error": "Query parameter is required"
}
```

**V3 search with an invalid page size** (`GET /v3/apps/?q=cleaner&limit=101`) returns HTTP `400` with `Content-Type: application/problem+json`. The example assumes `Accept-Language: en`.

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "Bad Request",
  "code": "validation_error",
  "errors": [
    {
      "path": "limit",
      "code": "max_value",
      "message": "Ensure this value is less than or equal to 100."
    }
  ]
}
```

Read `code` for branching and `errors[].path` to highlight an input. A V3 browse request without `q` succeeds.

### Execute and batch

**V2 request** to `POST /method/v2/execute/`

```json
{
  "code": [
    {"method": "marketplace.retrieve", "params": {"pk": 42}},
    {"method": "distribution.by_app", "params": {"app_id": 42}}
  ]
}
```

**V2 response (excerpt)**

```json
{
  "responses": [
    {"id": 42, "title": "Cleaner"},
    {"count": 1, "next": null, "previous": null, "results": [{"id": 17, "link": "/get_dist_file/17/"}]}
  ]
}
```

**V3 request** to `POST /v3/batch/`

```json
{
  "requests": [
    {"id": "app", "operation": "v3_apps_retrieve", "params": {"pk": 42}},
    {"id": "builds", "operation": "v3_apps_distributions_list", "params": {"pk": 42}}
  ]
}
```

**V3 response (excerpt)**

```json
{
  "results": [
    {"id": "app", "status": 200, "body": {"id": 42, "title": "Cleaner"}},
    {
      "id": "builds",
      "status": 200,
      "body": {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [{"id": 17, "download_url": "https://api.lunastore.app/v3/distributions/17/download/"}]
      }
    }
  ]
}
```

V2 results use their position in `responses`. V3 echoes the client-provided `id` and gives each result an HTTP-style `status`. For example, a missing app has item status `404` and a problem object in `body`, while the outer HTTP response stays `200`.

### Account and notifications

Login and refresh return `{"access":"…","refresh":"…"}` in both versions. In V3, save both values from each successful refresh. A successful `POST /v3/auth/token/revoke/` returns `204` with no body and invalidates the access tokens from that session. `GET /v3/me/` returns the caller's own profile.

V2 `GET /method/v2/user/getNotificationToken/` returns `{"token":"…","ws_url":"…"}` for connecting to LunaSpire. V3 `GET /v3/me/notifications/` accepts the LunaStore bearer token and returns the inbox directly.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "unread_count": 1,
  "results": [
    {
      "id": 68,
      "title": "Your app is published",
      "content": "Cleaner is now available in the catalog.",
      "type": "success",
      "created_at": "2026-01-15T12:00:00Z",
      "read_at": null
    }
  ]
}
```
