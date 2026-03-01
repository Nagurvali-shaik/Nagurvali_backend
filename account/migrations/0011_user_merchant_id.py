from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0010_user_marketer_commission"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="merchant_id",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
    ]

