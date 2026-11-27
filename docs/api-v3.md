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
3. Poll `GET /v3/me/notifications/?page=1&limit=20` for the inbox and `unread_count`. A notification with `read_at: null` is unread. Send `POST /v3/me/notifications/mark-all-read/` to mark the inbox read. Success returns HTTP 204. HTTP 503 means LunaSpire is temporarily unavailable.
4. Post `{"refresh":"…"}` to `/v3/auth/token/refresh/` and replace both saved tokens on success. Post the current refresh token to `/v3/auth/token/revoke/` to end the session.

## Batch catalog requests

Post to `/v3/batch/` with 1–25 read operations. Each has a unique client-supplied `id`, an OpenAPI `operationId` in `operation`, and optional scalar `params`. Detail operations take `pk`.

```json
{
  "requests": [
    {"id": "categories", "operation": "v3_categories_list", "params": {"limit": 10}},
    {"id": "versions", "operation": "v3_apps_distributions_list", "params": {"pk": 42}}
  ]
}
```

A valid batch returns HTTP 200 with a `results` array. Each result has `id`, `status`, and `body`. Inspect each status even when the outer request succeeds. Each item counts towards the request limit. Account, token, download, and write operations use their direct routes.

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

This release removes V1 RPC. Update clients using the table above and point monitoring at the V3 health endpoint. Deploy LunaSpire and Django from the matching release. Roll back the application and proxy configuration together if clients need to return to V1.

## V2 compatibility fixes

| Published contract or response | Correction in this release |
| --- | --- |
| V2 category objects expose the sprite class as `icon`. | Keep `icon` and add the standalone `icon_url`, pointing to a PNG where available. |
| The live OpenAPI describes category and collection app lists as single category or collection objects. | Describe the paginated app payload returned by the handlers. |
| The public API returned HTTP pagination links to HTTPS callers. | Use the configured public scheme when constructing links behind the proxy. |
| The generated schema omits the V2 JWT scheme and the Execute request and response shapes. | Declare bearer authentication and the existing Execute payload. |

The published [API documentation](https://docs.lunastore.app/api/) and [current OpenAPI](https://api.lunastore.app/schema/) are the comparison sources. Use `/schema/v2/` and `/docs/v2/` for the versioned V2 reference.
