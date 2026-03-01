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


def remap_legacy_shop_ids(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if "shop_shop" not in tables:
            return

        cursor.execute("SELECT id FROM shop_shop")
        rows = cursor.fetchall()

        id_map = {}
        for (shop_id,) in rows:
            shop_id_str = str(shop_id)
            if not _is_valid_uuid(shop_id_str):
                id_map[shop_id_str] = uuid.uuid4().hex

        if not id_map:
            return

        for old_id, new_id in id_map.items():
            cursor.execute(
                "UPDATE shop_shop SET id = %s WHERE id = %s",
                [new_id, old_id],
            )

        for table_name in tables:
            if table_name == "shop_shop":
                continue

            columns = {
                col.name for col in connection.introspection.get_table_description(cursor, table_name)
            }
            if "shop_id" not in columns:
                continue

            quoted_table = connection.ops.quote_name(table_name)
            for old_id, new_id in id_map.items():
                cursor.execute(
                    f"UPDATE {quoted_table} SET shop_id = %s WHERE shop_id = %s",
                    [new_id, old_id],
                )


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0002_alter_shop_id"),
    ]

    operations = [
        migrations.RunPython(remap_legacy_shop_ids, migrations.RunPython.noop),
    ]
