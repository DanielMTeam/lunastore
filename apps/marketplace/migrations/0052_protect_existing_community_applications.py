from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0051_protect_community_applications")]

    # A separate transaction releases the schema locks before updating existing rows.
    operations = [
        migrations.RunSQL(
            "SET LOCAL lock_timeout = '2s'",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "UPDATE marketplace_application SET community_protected = TRUE WHERE allow_community_distributions = TRUE",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
