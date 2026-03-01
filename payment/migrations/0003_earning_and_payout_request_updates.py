from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("order", "0002_order_orderitem"),
        ("payment", "0002_payoutrequest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="payoutrequest",
            name="order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payout_requests", to="order.order"),
        ),
        migrations.AlterField(
            model_name="payoutrequest",
            name="payment",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payout_requests", to="payment.payment"),
        ),
        migrations.AlterUniqueTogether(
            name="payoutrequest",
            unique_together=set(),
        ),
        migrations.CreateModel(
            name="Earning",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("role", models.CharField(blank=True, max_length=30)),
                ("merchant_id_snapshot", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(choices=[("AVAILABLE", "Available"), ("PAID_OUT", "Paid Out")], default="AVAILABLE", max_length=20)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="earnings", to="order.order")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="earnings", to="payment.payment")),
                ("payout_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="earning_items", to="payment.payoutrequest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="earnings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("user", "payment")},
            },
        ),
        migrations.AddIndex(
            model_name="earning",
            index=models.Index(fields=["status"], name="payment_earn_status_2f54a9_idx"),
        ),
        migrations.AddIndex(
            model_name="earning",
            index=models.Index(fields=["merchant_id_snapshot"], name="payment_earn_merchan_615778_idx"),
        ),
    ]

