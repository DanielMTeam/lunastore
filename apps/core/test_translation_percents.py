from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class TranslationPercentTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings_override = override_settings(BASE_DIR=self.root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.path = self.root / "locale/ru/LC_MESSAGES/django.po"
        self.path.parent.mkdir(parents=True)
        self.original = b'msgid "COUNT %(counter)s"\r\nmsgstr "%%(counter)s / 100%%"\r\n'
        self.path.write_bytes(self.original)

    def test_dry_run_does_not_modify_catalog(self):
        output = StringIO()
        call_command("fix_translation_percents", dry_run=True, stdout=output)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertIn("Found 1 escaped placeholders", output.getvalue())

    def test_fix_preserves_literal_percent_and_line_endings(self):
        call_command("fix_translation_percents", stdout=StringIO())
        self.assertEqual(
            self.path.read_bytes(),
            b'msgid "COUNT %(counter)s"\r\nmsgstr "%(counter)s / 100%%"\r\n',
        )

    def test_repeated_run_has_no_replacements(self):
        call_command("fix_translation_percents", stdout=StringIO())
        output = StringIO()
        call_command("fix_translation_percents", stdout=output)
        self.assertIn("Fixed 0 escaped placeholders", output.getvalue())
