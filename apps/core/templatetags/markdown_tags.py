from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter(name='render_markdown')
def render_markdown(value):
    if not value:
        return ""

    text = str(value)

    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    # Alerts
    def alert_repl(match):
        from django.utils.translation import gettext as _
        alert_type = match.group(1).lower()
        content = match.group(2)
        # remove leading "> " from each line
        content = re.sub(r'^> ?', '', content, flags=re.MULTILINE)

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

        return f'<div class="md-alert md-alert-{alert_type}"><strong>{display_type}</strong><br>{
            content.strip()}</div>'

    text = re.sub(
        r'^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\r?\n((?:>.*\r?\n?)*)',
        alert_repl,
        text,
        flags=re.MULTILINE)

    # replace newlines with <br>
    text = text.replace('\r\n', '<br>').replace('\n', '<br>')

    return mark_safe(text)
