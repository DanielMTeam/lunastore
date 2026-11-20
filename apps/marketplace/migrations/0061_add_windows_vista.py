from django.db import migrations


def add_windows_vista(apps, schema_editor):
    Platform = apps.get_model("marketplace", "Platform")
    Platform.objects.using(schema_editor.connection.alias).get_or_create(
        code="windows_vista", defaults={"name": "Windows Vista"}
    )


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0060_merge_platforms_and_access")]

    operations = [migrations.RunPython(add_windows_vista, migrations.RunPython.noop)]
