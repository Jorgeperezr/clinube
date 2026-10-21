"""
Activa pg_stat_statements: PostgreSQL apunta cuánto tiempo gasta cada
consulta, y `python manage.py consultas_lentas` lo enseña.

Solo en PostgreSQL y solo si el usuario puede crear extensiones (en el
contenedor de producción es el dueño de la base). Si no puede —una base
local con un usuario sin permisos, o SQLite en las pruebas— la migración
sigue sin ella: medir es útil, no imprescindible.
"""

from django.db import migrations, transaction


def crear(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    try:
        with transaction.atomic():
            schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [("common", "0012_modalidad_consultorio")]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
