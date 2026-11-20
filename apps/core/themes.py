"""Public-site themes; browser capability is checked locally before loading Windows 7."""
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    stylesheet: str
    requires_capabilities: bool = False


THEMES = (
    Theme("classic_light", _("THEME_CLASSIC_LIGHT"), ""),
    Theme("classic_dark", _("THEME_CLASSIC_DARK"), "css/darkthm.css"),
    Theme("windows7", _("THEME_WINDOWS7"), "css/windows7.css", True),
)
THEME_CHOICES = tuple((theme.id, theme.label) for theme in THEMES)
VALID_THEMES = frozenset(theme.id for theme in THEMES)


def resolve_theme(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.theme in VALID_THEMES:
        return user.theme
    return "classic_dark" if request.COOKIES.get("dark_theme") == "on" else "classic_light"


def theme_context(request):
    selected = resolve_theme(request)
    definition = next(theme for theme in THEMES if theme.id == selected)
    return {
        "selected_theme": selected,
        "selected_theme_css": definition.stylesheet,
        "site_themes": THEMES,
    }
