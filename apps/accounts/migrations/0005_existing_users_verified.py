from django.db import migrations


def mark_verified(apps, schema_editor):
    # Every account before visitor sign-up was made by an admin, whose invite or reset link proved the address.
    apps.get_model("accounts", "User").objects.update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_user_signup_fields")]

    operations = [migrations.RunPython(mark_verified, migrations.RunPython.noop)]
