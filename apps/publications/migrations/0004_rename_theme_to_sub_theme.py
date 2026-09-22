# Hand-written: Publication.theme -> Publication.sub_theme (a Theme FK must now reference
# a sub-theme specifically, enforced in PublicationSerializer.validate_sub_theme).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("publications", "0003_alter_publication_options"),
    ]

    operations = [
        migrations.RenameField(model_name="publication", old_name="theme", new_name="sub_theme"),
    ]
