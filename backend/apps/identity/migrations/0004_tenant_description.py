from django.db import migrations, models


def add_description_if_missing(apps, schema_editor):
    """The column already exists on databases provisioned outside this migration."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'identity_tenant' AND column_name = 'description'
            """
        )
        if cursor.fetchone():
            return
        cursor.execute(
            "ALTER TABLE identity_tenant ADD COLUMN description text NOT NULL DEFAULT ''"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0003_invitation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="tenant",
                    name="description",
                    field=models.TextField(blank=True, default=""),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_description_if_missing, migrations.RunPython.noop),
            ],
        ),
    ]
