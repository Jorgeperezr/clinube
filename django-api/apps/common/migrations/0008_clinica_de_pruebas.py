"""
Clínica de pruebas y funciones en prueba.

Una función nueva nace «en prueba»: solo la ven las clínicas de prueba
hasta que el Super Administrador la publica para todas (ver
apps/common/funcionalidades.py).

La clínica que ya existe —la primera que se creó, que es la que crea
`bootstrap` y la que usa `scripts/start-local.sh`— pasa a ser la de
pruebas. Si alguna ya estuviera marcada, no se toca nada. En una base
nueva no hay clínicas y esto no hace nada: allí la marca `bootstrap`.
"""

from django.db import migrations, models


def marcar_la_actual(apps, schema_editor):
    Tenant = apps.get_model("common", "Tenant")
    if Tenant.objects.filter(es_prueba=True).exists():
        return
    primera = Tenant.objects.order_by("created_at", "id").first()
    if primera is not None:
        primera.es_prueba = True
        primera.save(update_fields=["es_prueba"])


class Migration(migrations.Migration):
    dependencies = [("common", "0007_funciones_adicionales")]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="es_prueba",
            field=models.BooleanField(
                default=False, verbose_name="Clínica de pruebas",
                help_text=(
                    "Recibe las funciones nuevas antes que las demás. Lo que se "
                    "prueba aquí no llega a otras clínicas hasta publicarlo desde "
                    "Plataforma."
                ),
            ),
        ),
        migrations.AddField(
            model_name="platformconfiguration",
            name="funciones_publicadas",
            field=models.JSONField(blank=True, default=list, verbose_name="Funciones publicadas"),
        ),
        migrations.RunPython(marcar_la_actual, migrations.RunPython.noop),
    ]
