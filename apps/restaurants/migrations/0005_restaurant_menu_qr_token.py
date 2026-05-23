import uuid

from django.db import migrations, models


def assign_menu_qr_tokens(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    for restaurant in Restaurant.objects.all():
        if not restaurant.menu_qr_token:
            restaurant.menu_qr_token = uuid.uuid4()
            restaurant.save(update_fields=["menu_qr_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0004_company_legal_profile_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="menu_qr_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(assign_menu_qr_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="restaurant",
            name="menu_qr_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
