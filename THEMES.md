# Public-site themes

Themes are registered in apps/core/themes.py. Each entry defines its stable ID,
translated label, stylesheet and whether browser capability checks are required.
The Unfold admin theme is independent.

User.theme stores an explicit account preference. NULL retains the legacy
`dark_theme=on` cookie fallback; otherwise the default is classic_light.
Guests cannot change themes. Only the theme POST form on settings_ui.php writes
this field. The retired theme_switch.php route redirects to settings.

Windows 7 uses the supplied style7.css artwork and a bundled copy of its background
in staticfiles/img/themes/windows7-background.jpg. All rules are scoped to
html.theme-windows7. The original embedded PNG sprites are retained.

The synchronous head script checks background-size: cover and border-image with
an image, slice 30 and repeat round. It uses CSS.supports or CSSStyleDeclaration
assignment, and rejects IE document modes below 11. It enables the theme class immediately and inserts a parser-created stylesheet
from the synchronous head script, so the first paint waits for Windows 7 CSS.
CSS is loaded only when supported; a failed CSS load restores the base theme. Without JavaScript,
Windows 7 falls back to classic light. A fallback never updates the account.

The capability POST field is a usability check, not a security boundary: every
page independently gates stylesheet loading, even after a forged POST.

## Deployment

1. Apply user migration 0040 before restarting web, admin and API services.
   The nullable column is compatible with older code; adding it briefly requires
   ACCESS EXCLUSIVE. A 2-second lock timeout fails fast rather than waiting.
2. Run npm run babel:build and the normal collectstatic step. Compiled JavaScript
   is ignored by Git; source changes belong in staticfiles/js.
3. Restart services with the new code. No account backfill is required.

Rollback application code before reversing the migration. Reversing removes saved
preferences, and also uses the 2-second lock timeout.

## Validation

- python manage.py test apps.user.test_themes apps.user.tests apps.core.tests --noinput
- node --test tests/themes.test.cjs
- python manage.py makemigrations --check --dry-run
- python manage.py sqlmigrate user 0040
- npm run babel:build

Manual browser checks: verify both classic themes in IE6 and the Windows 7 theme
in current browsers and available Windows 7 browsers. On each, inspect settings,
both home layouts, catalog/search, application page and ratings, profile, publishing
forms, notifications and ThickBox. Check disabled JavaScript, rejected CSS
capabilities, stylesheet load failure, and switching devices with Windows 7 saved.

Automated capability tests simulate legacy behavior; they do not replace a real
IE6 or Windows 7 browser session.
