from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("order", "0002_order_orderitem"),
        ("payment", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PayoutRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("REQUESTED", "Requested"), ("PROCESSING", "Processing"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("REJECTED", "Rejected")], default="REQUESTED", max_length=20)),
                ("payout_method", models.CharField(blank=True, max_length=30)),
                ("payout_account", models.CharField(blank=True, max_length=150)),
                ("provider_reference", models.CharField(blank=True, max_length=150, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payout_requests", to="order.order")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payout_requests", to="payment.payment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payout_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("user", "payment")},
            },
        ),
        migrations.AddIndex(
            model_name="payoutrequest",
            index=models.Index(fields=["status"], name="payment_payo_status_7082e4_idx"),
        ),
        migrations.AddIndex(
            model_name="payoutrequest",
            index=models.Index(fields=["provider_reference"], name="payment_payo_provide_8cc9e6_idx"),
        ),
    ]

