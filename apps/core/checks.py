import os

from django.conf import settings
from django.core.checks import Tags, Warning, register

_PEM_CERT_MARKER = b"-----BEGIN CERTIFICATE-----"


def _ca_bundle_problem(path: str) -> str:
    if not os.path.isfile(path):
        return "file not found"
    try:
        with open(path, "rb") as fh:
            content = fh.read(1024 * 1024)
    except OSError as exc:
        return f"unreadable: {exc}"
    if _PEM_CERT_MARKER not in content:
        return "no PEM certificates (DER must be converted to PEM)"
    return ""


@register(Tags.security)
def oidc_tls_verification_check(app_configs, **kwargs):
    issues = []
    verify = getattr(settings, "OIDC_VERIFY_SSL", True)
    if verify is False:
        issues.append(Warning(
            "OIDC_VERIFY_SSL=False: TLS certificate verification is disabled for the OpenID provider",
            hint="Install the provider's certificate and set OIDC_VERIFY_SSL to its PEM path instead.",
            id="core.W001",
        ))
    elif isinstance(verify, str) and verify:
        problem = _ca_bundle_problem(verify)
        if problem:
            issues.append(Warning(
                f"OIDC_VERIFY_SSL CA bundle problem ({problem}): {verify}",
                hint="Set OIDC_VERIFY_SSL to a valid PEM file with certificates.",
                id="core.W002",
            ))
    return issues


@register(Tags.security)
def lunapassport_tls_verification_check(app_configs, **kwargs):
    from apps.user.services import lunapassport

    try:
        verify = lunapassport.get_verify()
    except lunapassport.LunaPassportError as exc:
        return [Warning(
            f"LunaPassport TLS configuration problem: {exc}",
            hint="Set LUNAPASSPORT_CA_BUNDLE to a valid PEM file or remove it.",
            id="core.W003",
        )]
    except Exception:
        # constance/redis unavailable during early startup — skip the check
        return []
    if verify is False:
        return [Warning(
            "LUNAPASSPORT_VERIFY_SSL=False: TLS certificate verification is disabled for LunaPassport",
            hint="Install the passport certificate and set LUNAPASSPORT_CA_BUNDLE to its PEM path instead.",
            id="core.W004",
        )]
    return []
