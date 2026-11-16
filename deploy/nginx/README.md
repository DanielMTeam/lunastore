# Manual mirrors with systemd Nginx and Docker Django

`lunastore.app` and `api.lunastore.app` use the primary API/CDN settings.
`ru.lunastore.app` and `api.ru.lunastore.app` select the corresponding
`GEO_DOMAIN_OVERRIDES` entry by hostname. The visitor's country is used for
noSpam and analytics, independently of the selected mirror.

Keep `GEO_DOMAIN_PROXY_ENABLED=True` and
`GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS=False` for manual mirrors. Include all
served web/API hostnames in Django `ALLOWED_HOSTS`.

## Main domains behind Cloudflare; RU mirror accessed directly

Copy `cloudflare-realip.conf` to
`/etc/nginx/snippets/lunastore-cloudflare-realip.conf`, then include it inside
the existing server blocks hosting Cloudflare-proxied domains:

```nginx
include /etc/nginx/snippets/lunastore-cloudflare-realip.conf;
```

The same server block may also serve the direct RU mirror. Only socket peers
in the verified Cloudflare ranges can replace `$remote_addr`; public clients
connecting directly to the mirror cannot supply their own client IP.
Keep the ranges synchronized with Cloudflare's published IPv4/IPv6 lists.

In the proxy snippet included by each Django location, replace the header
directives below rather than adding duplicates. Keep existing timeouts and
buffer settings. Without Nginx GeoIP2, Django performs cached GeoIP lookups:

```nginx
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Country-Code "";
proxy_set_header CF-IPCountry "";
proxy_set_header CF-Connecting-IP "";
proxy_set_header X-GeoIP-Country "";
proxy_set_header X-GeoIP-Country-Code "";
```

If using the supplied Nginx GeoIP2 example, `X-Country-Code` is instead set to
the country computed from the restored `$remote_addr`.

Set Django `TRUSTED_PROXIES` to the exact Nginx peer address observed in Django
`REMOTE_ADDR`. With host Nginx forwarding to Docker, this may be the Docker
bridge gateway rather than loopback. For example, **only if verified**:

```dotenv
TRUSTED_PROXIES="172.18.0.1/32"
```

Django trusts Nginx's peer address; Nginx trusts Cloudflare's edge addresses.
Do not add all private networks or Cloudflare's ranges to Django merely to
account for this topology. Requests to direct RU mirrors retain their real IP.

Validate with `nginx -t` before reloading Nginx. These files are deployment
examples; updating the PR does not update `/etc/nginx` on the server.


If Nginx also serves the LunaSpire hostname, use
`access_log /var/log/nginx/lunaspire-access.log lunastore_safe;` on that host.
The format above omits the entire query string for notification requests. The
bundled Caddy configuration leaves access logging off. If enabling Caddy access
logs on a LunaSpire host, filter the `token` query parameter before logging.


### Security release with OIDC and API session changes

1. Apply the additive `user.0042_api_session_and_oidc_identity` migration before
   switching application instances. Verify the SQL with
   `python manage.py sqlmigrate user 0042` on staging.
2. Set `OIDC_EXPECTED_ISSUER` to the exact Authentik issuer and
   `OIDC_REQUIRED_ROLE` to the required value in the UserInfo `groups` array.
   Configure the Authentik scope mapping to emit this array. Using a superuser,
   create an OIDC identity binding for each approved staff account with the
   verified issuer and subject. Review staff and moderator memberships before
   switching and verify local admin login on staging.
3. Switch web, admin and API instances together. Clients with existing JWTs
   must authenticate again. Existing OIDC sessions are logged out on their next
   request. Verify staff login and JWT issue, refresh and revocation after cutover.
4. Verify the host proxy can still reach Django on loopback, then verify direct
   remote connections to the published backend ports fail. Previously issued
   download URLs may work until their signatures expire.
