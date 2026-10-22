from django.db import migrations


def cerrar_las_que_esperaban_codigo(apps, schema_editor):
    """
    Las altas que se quedaron esperando el código del correo nunca se
    confirmaron y nadie las veía en Plataforma. Con la aprobación ya no
    hay ese paso: se cierran como descartadas, sin borrarlas.
    """
    Solicitud = apps.get_model("common", "SolicitudClinica")
    Solicitud.objects.filter(estado="verificando").update(
        estado="descartada", nota="Sin confirmar el correo (alta anterior a la aprobación).")


class Migration(migrations.Migration):
    """Va sola: en PostgreSQL, actualizar filas y alterar la tabla en la misma transacción falla."""

    dependencies = [
        ("common", "0013_pg_stat_statements"),
    ]

    operations = [
        migrations.RunPython(cerrar_las_que_esperaban_codigo, migrations.RunPython.noop),
    ]
