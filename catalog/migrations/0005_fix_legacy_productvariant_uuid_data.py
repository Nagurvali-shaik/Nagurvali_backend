import uuid

from django.db import migrations


def _is_valid_uuid(value):
    if value is None:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def remap_legacy_variant_ids(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if "catalog_productvariant" not in tables:
            return

        cursor.execute("SELECT id FROM catalog_productvariant")
        rows = cursor.fetchall()

        id_map = {}
        for (variant_id,) in rows:
            variant_id_str = str(variant_id)
            if not _is_valid_uuid(variant_id_str):
                id_map[variant_id_str] = uuid.uuid4().hex

        if not id_map:
            return

        for old_id, new_id in id_map.items():
            cursor.execute(
                "UPDATE catalog_productvariant SET id = %s WHERE id = %s",
                [new_id, old_id],
            )

        for table_name in tables:
            if table_name == "catalog_productvariant":
                continue

            columns = {
                col.name for col in connection.introspection.get_table_description(cursor, table_name)
            }
            if "variant_id" not in columns:
                continue

            quoted_table = connection.ops.quote_name(table_name)
            for old_id, new_id in id_map.items():
                cursor.execute(
                    f"UPDATE {quoted_table} SET variant_id = %s WHERE variant_id = %s",
                    [new_id, old_id],
                )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_alter_productvariant_id"),
    ]

    operations = [
        migrations.RunPython(remap_legacy_variant_ids, migrations.RunPython.noop),
    ]
