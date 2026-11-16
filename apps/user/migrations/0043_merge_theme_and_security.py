from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0040_user_theme"),
        ("user", "0042_api_session_and_oidc_identity"),
    ]

    operations = []
