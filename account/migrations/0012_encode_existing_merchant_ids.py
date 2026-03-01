import base64

from django.db import migrations


PREFIX = "enc:"


def _encode(value: str) -> str:
    raw = (value or "").strip()
    if not raw or raw.startswith(PREFIX):
        return raw
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{encoded}"


def forwards(apps, schema_editor):
    User = apps.get_model("account", "User")
    for user in User.objects.exclude(merchant_id__isnull=True).exclude(merchant_id=""):
        encoded = _encode(user.merchant_id)
        if encoded != user.merchant_id:
            user.merchant_id = encoded
            user.save(update_fields=["merchant_id"])


def backwards(apps, schema_editor):
    # Keep data as-is on rollback.
    return


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0011_user_merchant_id"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

