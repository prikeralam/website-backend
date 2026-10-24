from django.db import migrations, models


def deadlines_are_not_rolling(apps, schema_editor):
    # An opening with a deadline was saved as rolling because rolling was the default, which hid its deadline
    # (the live Research Associate/Assistant opening, closing 2026-11-10). Only rows with a deadline are touched.
    JobOpening = apps.get_model("careers", "JobOpening")
    JobOpening.objects.filter(deadline__isnull=False, rolling=True).update(rolling=False)


class Migration(migrations.Migration):

    dependencies = [
        ("careers", "0004_cover_letter_writing_sample_jd"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobopening",
            name="rolling",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(deadlines_are_not_rolling, migrations.RunPython.noop),
    ]
