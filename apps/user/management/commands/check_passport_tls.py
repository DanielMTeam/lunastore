import socket
import ssl
from urllib.parse import urlparse

import requests
from cryptography import x509
from django.core.management.base import BaseCommand

from apps.user.services import lunapassport


class Command(BaseCommand):
    help = "Diagnose LunaPassport TLS: effective CA bundle, presented certificate and trust check"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="Connection timeout in seconds (default: 10)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]

        try:
            base_url = lunapassport.get_base_url()
        except lunapassport.LunaPassportError as exc:
            self.stdout.write(self.style.ERROR(f"LunaPassport base URL is not configured: {exc}"))
            return

        try:
            ca_bundle = lunapassport.get_ca_bundle()
            verify = lunapassport.get_verify()
        except lunapassport.LunaPassportError as exc:
            self.stdout.write(self.style.ERROR(f"CA bundle problem: {exc}"))
            return

        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        self.stdout.write(f"base URL:  {base_url}")
        self.stdout.write(f"CA bundle: {ca_bundle or '-'}")
        self.stdout.write(f"verify:    {verify!r}")
        self.stdout.write("policy:    X509_STRICT off, SECLEVEL=0 (pinned private CA)")

        if parsed.scheme != "https":
            self.stdout.write(self.style.WARNING("base URL is not https — TLS checks skipped"))
            return

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        chain_der = []
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                    der = tls_sock.getpeercert(binary_form=True)
                    get_chain = getattr(tls_sock, "get_unverified_chain", None)
                    if callable(get_chain):
                        for item in get_chain():
                            chain_der.append(item if isinstance(item, bytes) else item.public_bytes())
        except OSError as exc:
            self.stdout.write(self.style.ERROR(f"TLS connection to {host}:{port} failed: {exc}"))
            return

        cert = x509.load_der_x509_certificate(der)
        self.stdout.write(f"subject:   {cert.subject.rfc4514_string()}")
        self.stdout.write(f"issuer:    {cert.issuer.rfc4514_string()}")
        self.stdout.write(f"valid:     {cert.not_valid_before_utc} — {cert.not_valid_after_utc}")
        self.stdout.write(f"self-signed: {cert.subject == cert.issuer}")
        try:
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            dns_names = san.get_values_for_type(x509.DNSName)
            if dns_names:
                self.stdout.write(f"SAN DNS:   {', '.join(dns_names)}")
        except x509.ExtensionNotFound:
            pass

        if len(chain_der) > 1:
            self.stdout.write(f"server chain ({len(chain_der)} certs, root may be missing):")
            for index, chain_item in enumerate(chain_der[1:], start=1):
                chain_cert = x509.load_der_x509_certificate(chain_item)
                self.stdout.write(
                    f"  [{index}] {chain_cert.subject.rfc4514_string()} "
                    f"(issuer: {chain_cert.issuer.rfc4514_string()})"
                )

        if verify is False:
            self.stdout.write(self.style.WARNING(
                "TLS verification is DISABLED — insecure, do not use in production"
            ))
            return

        try:
            check_context = (
                lunapassport.build_tls_context(verify)
                if isinstance(verify, str)
                else ssl.create_default_context()
            )
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with check_context.wrap_socket(sock, server_hostname=host):
                    pass
        except ssl.SSLError as exc:
            self.stdout.write(self.style.ERROR(f"TLS verification FAILED: {exc}"))
            self.stdout.write(
                "hint: LUNAPASSPORT_CA_BUNDLE must contain the issuing CA certificate (Root Authority), "
                "not the leaf/server certificate; the hostname must also match the base URL"
            )
            return

        self.stdout.write(self.style.SUCCESS("TLS verification: OK"))

        try:
            userinfo_url = lunapassport.get_userinfo_url()
            with lunapassport.build_http_session(verify) as session:
                response = session.get(userinfo_url, timeout=timeout, verify=verify)
            self.stdout.write(f"HTTP probe {userinfo_url}: {response.status_code}")
        except requests.RequestException as exc:
            self.stdout.write(self.style.ERROR(f"HTTP probe failed: {exc}"))
