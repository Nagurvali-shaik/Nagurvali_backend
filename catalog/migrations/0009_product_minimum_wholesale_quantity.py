from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_product_supplier"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="minimum_wholesale_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
    ]

