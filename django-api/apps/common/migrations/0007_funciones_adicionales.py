"""
El odontograma 3D y las rachas y logros pasan a ser funciones
«adicionales»: una clínica nueva ya no las trae.

Las clínicas que YA existen no deben perderlas por eso. Hasta ahora una
clave ausente en `funcionalidades` se leía como encendida; desde esta
versión se leería como apagada. Aquí se deja escrito, para cada clínica
existente, el valor que tenía de hecho, de modo que nada cambia para
ellas.
"""

from django.db import migrations

ADICIONALES = ("odontograma_3d", "logros")


def conservar(apps, schema_editor):
    Tenant = apps.get_model("common", "Tenant")
    for tenant in Tenant.objects.all():
        f = dict(tenant.funcionalidades or {})
        cambio = False
        for clave in ADICIONALES:
            if clave not in f:
                f[clave] = True
                cambio = True
        if cambio:
            tenant.funcionalidades = f
            tenant.save(update_fields=["funcionalidades"])


class Migration(migrations.Migration):
    dependencies = [("common", "0006_textos_legales")]
    operations = [migrations.RunPython(conservar, migrations.RunPython.noop)]
