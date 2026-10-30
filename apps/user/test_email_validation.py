"""DNS failures must not poison the email validation cache."""
from unittest.mock import patch

import dns.exception
import dns.resolver
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .validators import validate_email_mx


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class EmailMXValidationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("apps.user.validators.dns.resolver.Resolver")
        self.resolver_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.resolver = self.resolver_class.return_value

    def test_success_is_cached_and_domains_are_case_insensitive(self):
        validate_email_mx("person@GMAIL.COM")
        validate_email_mx("another@gmail.com")
        self.resolver.resolve.assert_called_once_with("gmail.com", "MX")
        self.assertTrue(cache.get("mx_record_v2_gmail.com"))
        self.assertEqual(self.resolver.timeout, 2.0)
        self.assertEqual(self.resolver.lifetime, 2.0)

    def test_definitive_dns_failures_are_rejected_and_cached(self):
        for failure in (dns.resolver.NXDOMAIN(), dns.resolver.NoAnswer()):
            with self.subTest(failure=type(failure).__name__):
                cache.clear()
                self.resolver.resolve.reset_mock()
                self.resolver.resolve.side_effect = failure
                for _ in range(2):
                    with self.assertRaises(ValidationError):
                        validate_email_mx("person@mail.example.org")
                self.resolver.resolve.assert_called_once()
                self.assertIs(cache.get("mx_record_v2_mail.example.org"), False)

    def test_temporary_dns_failures_are_not_rejected_or_cached(self):
        for failure in (
            dns.exception.Timeout(), dns.resolver.LifetimeTimeout(),
            dns.resolver.NoNameservers(), OSError("network unavailable"),
        ):
            with self.subTest(failure=type(failure).__name__):
                cache.clear()
                self.resolver.resolve.reset_mock()
                self.resolver.resolve.side_effect = failure
                for _ in range(2):
                    validate_email_mx("person@gmail.com")
                self.assertEqual(self.resolver.resolve.call_count, 2)
                self.assertIsNone(cache.get("mx_record_v2_gmail.com"))

    def test_missing_resolver_configuration_is_not_cached(self):
        self.resolver_class.side_effect = dns.resolver.NoResolverConfiguration()
        validate_email_mx("person@gmail.com")
        self.assertIsNone(cache.get("mx_record_v2_gmail.com"))

    def test_legacy_negative_cache_does_not_reject_gmail(self):
        cache.set("mx_record_gmail.com", False, 3600)
        validate_email_mx("person@gmail.com")
        self.resolver.resolve.assert_called_once_with("gmail.com", "MX")
        self.assertTrue(cache.get("mx_record_v2_gmail.com"))

    def test_dns_recovers_after_timeout(self):
        self.resolver.resolve.side_effect = [dns.exception.Timeout(), object()]
        validate_email_mx("person@gmail.com")
        self.assertIsNone(cache.get("mx_record_v2_gmail.com"))
        validate_email_mx("person@gmail.com")
        self.assertTrue(cache.get("mx_record_v2_gmail.com"))

    def test_real_failure_after_timeout_still_rejects(self):
        self.resolver.resolve.side_effect = [dns.exception.Timeout(), dns.resolver.NXDOMAIN()]
        validate_email_mx("person@mail.example.org")
        with self.assertRaises(ValidationError):
            validate_email_mx("person@mail.example.org")

    def test_invalid_syntax_aliases_and_disposable_domains_remain_blocked(self):
        for address in ("broken-email", "person+alias@gmail.com", "person@disposable.example.org"):
            with self.subTest(address=address), patch(
                "apps.user.validators.blocklist", {"disposable.example.org"},
            ):
                with self.assertRaises(ValidationError):
                    validate_email_mx(address)
        self.resolver_class.assert_not_called()
