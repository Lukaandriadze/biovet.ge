from django.core.management.color import no_style
from django.db import connection, migrations


def reset_product_sequence(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    statements = connection.ops.sequence_reset_sql(no_style(), [Product])
    with connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_alter_product_status"),
    ]

    operations = [
        migrations.RunPython(reset_product_sequence, migrations.RunPython.noop),
    ]