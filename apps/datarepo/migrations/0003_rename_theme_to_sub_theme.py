# Hand-written: Dataset.theme -> Dataset.sub_theme (a Theme FK must now reference a
# sub-theme specifically, enforced in DatasetSerializer.validate_sub_theme).
# Dashboard.theme is deliberately untouched — only Dataset/Publication were asked for.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("datarepo", "0002_alter_dashboard_options_alter_dataset_options"),
    ]

    operations = [
        migrations.RenameField(model_name="dataset", old_name="theme", new_name="sub_theme"),
    ]
