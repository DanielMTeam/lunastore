from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0039_collection_collectionitem_collectionfavorite"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx",
        ),
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx-ru",
        ),
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx-en",
        ),
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx-uk",
        ),
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx-be",
        ),
        migrations.RemoveIndex(
            model_name="application",
            name="app_trgm_idx-kk",
        ),
    ]
