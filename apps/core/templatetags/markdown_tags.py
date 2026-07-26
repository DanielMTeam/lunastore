from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
import logging
import re

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name='render_markdown')
def render_markdown(value):
    """render limited markdown after escaping user html."""
    if not value:
        return ""

    try:
        # escape first so raw html/js cannot reach mark_safe
        text = escape(str(value))

        # bold
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # italic
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

        # alerts ("> " becomes "&gt; " after escape)
        def alert_repl(match):
            from django.utils.translation import gettext as _
            alert_type = match.group(1).lower()
            content = match.group(2)
            content = re.sub(r'^&gt; ?', '', content, flags=re.MULTILINE)

            if alert_type == "note":
                display_type = _("MD_ALERT_NOTE")
            elif alert_type == "tip":
                display_type = _("MD_ALERT_TIP")
            elif alert_type == "important":
                display_type = _("MD_ALERT_IMPORTANT")
            elif alert_type == "warning":
                display_type = _("MD_ALERT_WARNING")
            elif alert_type == "caution":
                display_type = _("MD_ALERT_CAUTION")
            else:
                display_type = alert_type.capitalize()

            return (
                f'<div class="md-alert md-alert-{alert_type}">'
                f'<strong>{display_type}</strong><br>{content.strip()}</div>'
            )

        text = re.sub(
            r'^&gt; \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\r?\n((?:&gt; ?.*\r?\n?)*)',
            alert_repl,
            text,
            flags=re.MULTILINE,
        )

        # replace newlines with <br>
        text = text.replace('\r\n', '<br>').replace('\n', '<br>')

        return mark_safe(text)
    except Exception:
        logger.exception("failed to render markdown")
        return escape(str(value)) if value else ""
