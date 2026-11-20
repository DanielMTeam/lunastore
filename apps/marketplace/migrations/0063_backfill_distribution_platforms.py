from django.db import migrations


def copy_platforms(apps, schema_editor):
    alias = schema_editor.connection.alias
    for name in ("Distribution", "DistributionCreateRequests", "DistributionEditRequests"):
        model = apps.get_model("marketplace", name)
        through = model.platforms.through
        source_field = model._meta.model_name + "_id"
        last_pk = 0
        while True:
            rows = list(model._base_manager.using(alias).filter(pk__gt=last_pk).order_by("pk")
                        .values_list("pk", "platform_id")[:1000])
            if not rows:
                break
            through.objects.using(alias).bulk_create(
                [through(**{source_field: pk, "platform_id": platform_id}) for pk, platform_id in rows if platform_id],
                ignore_conflicts=True,
            )
            last_pk = rows[-1][0]


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("marketplace", "0062_distribution_platforms_and_more")]
    operations = [migrations.RunPython(copy_platforms, migrations.RunPython.noop, atomic=False)]
