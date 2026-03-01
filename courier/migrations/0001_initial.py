from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("order", "0002_order_orderitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourierPartner",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("provider_code", models.CharField(max_length=50, unique=True)),
                ("api_base_url", models.URLField(blank=True)),
                ("api_key", models.CharField(blank=True, max_length=255)),
                ("webhook_secret", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["priority", "name"]},
        ),
        migrations.CreateModel(
            name="Shipment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("CREATED", "Created"), ("PICKED_UP", "Picked Up"), ("IN_TRANSIT", "In Transit"), ("OUT_FOR_DELIVERY", "Out for Delivery"), ("DELIVERED", "Delivered"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=30)),
                ("external_shipment_id", models.CharField(blank=True, max_length=150)),
                ("external_tracking_id", models.CharField(blank=True, db_index=True, max_length=150)),
                ("last_event", models.CharField(blank=True, max_length=100)),
                ("last_payload", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("courier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shipments", to="courier.courierpartner")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="shipment", to="order.order")),
            ],
        ),
        migrations.AddIndex(
            model_name="shipment",
            index=models.Index(fields=["status"], name="courier_shi_status_03d7de_idx"),
        ),
        migrations.AddIndex(
            model_name="shipment",
            index=models.Index(fields=["external_tracking_id"], name="courier_shi_externa_39e8ea_idx"),
        ),
    ]

