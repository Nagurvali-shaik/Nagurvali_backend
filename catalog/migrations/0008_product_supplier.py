from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0011_user_merchant_id"),
        ("catalog", "0007_product_shop_owner_price_product_supplier_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="supplier",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"role": "SUPPLIER"},
                null=True,
                on_delete=models.SET_NULL,
                related_name="supplied_products",
                to="account.user",
            ),
        ),
    ]

